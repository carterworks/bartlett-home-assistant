"""Tests for Bartlett KilnAid config-entry setup lifecycles."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PACKAGE_NAME = "custom_components.bartlett_kilnaid"
PACKAGE_PATH = Path(__file__).parents[1] / "custom_components" / "bartlett_kilnaid"

if PACKAGE_NAME not in sys.modules:
    package = ModuleType(PACKAGE_NAME)
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules[PACKAGE_NAME] = package


class FakeConfigEntryNotReady(Exception):
    """Stand in for Home Assistant's setup retry signal."""


class FakeConfigEntry:
    """Config entry with the fields used during setup."""

    def __init__(self) -> None:
        self.entry_id = "entry-id"
        self.data = {"email": "user@example.com", "token": "test-token"}
        self.runtime_data = None

    @classmethod
    def __class_getitem__(cls, item):
        return cls


class FakeConfigEntries:
    """Record platform setup and unload calls."""

    def __init__(self) -> None:
        self.forwarded = False

    async def async_forward_entry_setups(self, entry, platforms) -> None:
        self.forwarded = True

    async def async_unload_platforms(self, entry, platforms) -> bool:
        return True


class FakeHomeAssistant:
    """Home Assistant state needed by integration setup."""

    def __init__(self, session) -> None:
        self.data: dict[str, Any] = {}
        self.config_entries = FakeConfigEntries()
        self.session = session


class FakeResponse:
    """Minimal asynchronous HTTP response."""

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
    """Return queued responses while recording requests."""

    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.requests: list[str] = []

    def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.requests.append(url)
        return self.responses.pop(0)


def _install_home_assistant_stubs() -> None:
    """Install the Home Assistant surface used by setup and the coordinator."""
    homeassistant = sys.modules.setdefault("homeassistant", ModuleType("homeassistant"))
    config_entries = sys.modules.setdefault(
        "homeassistant.config_entries", ModuleType("homeassistant.config_entries")
    )
    config_entries.ConfigEntry = FakeConfigEntry
    const = sys.modules.setdefault(
        "homeassistant.const", ModuleType("homeassistant.const")
    )
    const.CONF_EMAIL = "email"
    core = sys.modules.setdefault(
        "homeassistant.core", ModuleType("homeassistant.core")
    )
    core.HomeAssistant = FakeHomeAssistant
    exceptions = sys.modules.setdefault(
        "homeassistant.exceptions", ModuleType("homeassistant.exceptions")
    )
    exceptions.ConfigEntryNotReady = FakeConfigEntryNotReady
    helpers = sys.modules.setdefault(
        "homeassistant.helpers", ModuleType("homeassistant.helpers")
    )
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: hass.session
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    homeassistant.config_entries = config_entries
    homeassistant.const = const
    homeassistant.core = core
    homeassistant.exceptions = exceptions
    homeassistant.helpers = helpers


_install_home_assistant_stubs()
api = __import__(f"{PACKAGE_NAME}.api", fromlist=["api"])
coordinator_module = __import__(f"{PACKAGE_NAME}.coordinator", fromlist=["coordinator"])


async def _first_refresh(self) -> None:
    """Model HA first refresh converting UpdateFailed to ConfigEntryNotReady."""
    try:
        self.data = await self._async_update_data()
    except Exception as err:
        raise FakeConfigEntryNotReady from err


coordinator_module.BartlettCoordinator.async_config_entry_first_refresh = _first_refresh

spec = importlib.util.spec_from_file_location(
    PACKAGE_NAME,
    PACKAGE_PATH / "__init__.py",
    submodule_search_locations=[str(PACKAGE_PATH)],
)
assert spec and spec.loader
integration = importlib.util.module_from_spec(spec)
stub_package = sys.modules[PACKAGE_NAME]
try:
    sys.modules[PACKAGE_NAME] = integration
    spec.loader.exec_module(integration)
finally:
    sys.modules[PACKAGE_NAME] = stub_package


def _claimed_kiln_responses() -> tuple[FakeResponse, FakeResponse, FakeResponse]:
    return (
        FakeResponse([{"serial_number": "GENERIC", "kiln_id": "external-id"}]),
        FakeResponse([{"serialNumber": "GENERIC", "externalId": "external-id"}]),
        FakeResponse([{"externalId": "external-id", "mode": "Idle"}]),
    )


def test_startup_retry_waits_for_persisted_rate_limit(monkeypatch) -> None:
    async def run_test() -> None:
        session = FakeSession(
            FakeResponse({}, status=429, headers={"Retry-After": "60"}),
            *_claimed_kiln_responses(),
        )
        hass = FakeHomeAssistant(session)
        entry = FakeConfigEntry()

        with pytest.raises(FakeConfigEntryNotReady):
            await integration.async_setup_entry(hass, entry)

        wait_started = asyncio.Event()
        release_wait = asyncio.Event()
        observed_delay = 0.0

        async def fake_sleep(delay: float) -> None:
            nonlocal observed_delay
            observed_delay = delay
            wait_started.set()
            await release_wait.wait()

        monkeypatch.setattr(api, "sleep", fake_sleep)
        retry = asyncio.create_task(integration.async_setup_entry(hass, entry))
        await wait_started.wait()

        assert len(session.requests) == 1
        assert observed_delay > 59

        hass.data["bartlett_kilnaid"][entry.entry_id].deadline = 0
        release_wait.set()
        assert await retry
        assert hass.config_entries.forwarded

    asyncio.run(run_test())


def test_setup_retries_inventory_after_kiln_is_claimed() -> None:
    async def run_test() -> None:
        session = FakeSession(FakeResponse([]), *_claimed_kiln_responses())
        hass = FakeHomeAssistant(session)
        entry = FakeConfigEntry()

        with pytest.raises(FakeConfigEntryNotReady, match="No claimed"):
            await integration.async_setup_entry(hass, entry)

        assert await integration.async_setup_entry(hass, entry)
        assert session.requests.count("https://kiln.bartinst.com/kilns/settings") == 2
        assert entry.runtime_data.data
        assert hass.config_entries.forwarded

    asyncio.run(run_test())
