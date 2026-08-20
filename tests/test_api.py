"""Tests for Bartlett KilnAid response parsing."""

import asyncio
import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

# Load the pure API module without importing the Home Assistant integration runtime.
package = ModuleType("custom_components.bartlett_kilnaid")
package.__path__ = [
    str(Path(__file__).parents[1] / "custom_components" / "bartlett_kilnaid")
]
sys.modules[package.__name__] = package
api = import_module("custom_components.bartlett_kilnaid.api")
parse_kiln = api.parse_kiln
BartlettApiClient = api.BartlettApiClient
BartlettRateLimitError = api.BartlettRateLimitError


class FakeResponse:
    """Minimal aiohttp response used by the API client tests."""

    def __init__(
        self,
        payload: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.payload = payload
        self.status = status
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def json(self, *, content_type=None) -> Any:
        return self.payload

    async def read(self) -> bytes:
        return b""


class FakeSession:
    """Record requests and return queued responses."""

    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)


def test_parse_single_zone_kiln() -> None:
    kiln = parse_kiln(
        {
            "updatedAt": datetime.now(UTC).isoformat(),
            "externalId": "kiln-id",
            "temperatureScale": "F",
            "numZones": 1,
            "mode": "Firing",
            "t2": "1584",
            "setPoint": "1600",
            "programName": "Cone 6 Medium",
            "segment": "Ramp 3",
            "firingTime": "2:05",
            "holdRemainingTime": "0:10",
            "alarmAbbreviation": "OFF",
        },
        {
            "serialNumber": "GEN2-123",
            "externalId": "kiln-id",
            "name": "Studio Kiln",
            "firmwareVersion": "1.2.3",
            "numFirings": 5,
        },
    )

    assert kiln.name == "Studio Kiln"
    assert kiln.zone_temperatures == (None, 1584.0, None)
    assert kiln.set_point == 1600.0
    assert kiln.firing_minutes == 125
    assert kiln.hold_minutes == 10
    assert kiln.online


def test_parse_celsius_kiln() -> None:
    kiln = parse_kiln(
        {
            "temperatureScale": "C",
            "numZones": 3,
            "mode": "Idle",
            "t1": 100,
            "t2": 200,
            "t3": 300,
            "setPoint": 400,
        },
        {"serialNumber": "GEN2-456"},
    )

    assert kiln.zone_temperatures == (100.0, 200.0, 300.0)
    assert kiln.set_point == 400.0
    assert kiln.temperature_scale == "C"
    assert not kiln.online


def test_client_uses_compact_status_endpoint_and_current_auth_headers() -> None:
    session = FakeSession(
        FakeResponse(
            [
                {
                    "serial_number": "GENERIC-123",
                    "kiln_id": "external-id",
                    "name": "Studio Kiln",
                }
            ]
        ),
        FakeResponse(
            [
                {
                    "serialNumber": "GENERIC-123",
                    "externalId": "external-id",
                    "firmwareVersion": "1.2.3",
                    "numZones": 1,
                }
            ]
        ),
        FakeResponse(
            [
                {
                    "externalId": "external-id",
                    "updatedAt": datetime.now(UTC).isoformat(),
                    "mode": "Idle",
                    "t2": 72,
                }
            ]
        ),
        FakeResponse(
            [
                {
                    "externalId": "external-id",
                    "updatedAt": datetime.now(UTC).isoformat(),
                    "mode": "Idle",
                    "t2": 73,
                }
            ]
        ),
    )
    client = BartlettApiClient(session, "user@example.com", "test-token")

    first = asyncio.run(client.async_get_kilns())
    second = asyncio.run(client.async_get_kilns())

    assert first["GENERIC-123"].zone_temperatures[1] == 72
    assert second["GENERIC-123"].zone_temperatures[1] == 73
    assert [request[1] for request in session.requests] == [
        "https://kiln.bartinst.com/kilns/settings",
        "https://kiln.bartinst.com/kilnaid-data/settings",
        "https://kiln.bartinst.com/kilnaid-data/status",
        "https://kiln.bartinst.com/kilnaid-data/status",
    ]
    for _, _, kwargs in session.requests:
        assert "params" not in kwargs
        assert kwargs["headers"]["auth-token"] == "binst-cookie=test-token"
        assert kwargs["headers"]["email"] == "user@example.com"


def test_client_handles_account_without_claimed_kilns() -> None:
    session = FakeSession(FakeResponse([]))
    client = BartlettApiClient(session, "user@example.com", "test-token")

    assert asyncio.run(client.async_get_kilns()) == {}
    assert len(session.requests) == 1


def test_client_honors_rate_limit_retry_after() -> None:
    session = FakeSession(FakeResponse({}, status=429, headers={"Retry-After": "137"}))
    client = BartlettApiClient(session, "user@example.com", "test-token")

    with pytest.raises(BartlettRateLimitError) as raised:
        asyncio.run(client.async_get_kilns())

    assert raised.value.retry_after == 137


def test_client_uses_safe_fallback_for_invalid_retry_after() -> None:
    session = FakeSession(
        FakeResponse({}, status=429, headers={"Retry-After": "invalid"})
    )
    client = BartlettApiClient(session, "user@example.com", "test-token")

    with pytest.raises(BartlettRateLimitError) as raised:
        asyncio.run(client.async_get_kilns())

    assert raised.value.retry_after == 300
