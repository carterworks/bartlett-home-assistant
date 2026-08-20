"""Tests for Bartlett KilnAid polling coordination."""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

package_name = "custom_components.bartlett_kilnaid"
if package_name not in sys.modules:
    package = ModuleType(package_name)
    package.__path__ = [
        str(Path(__file__).parents[1] / "custom_components" / "bartlett_kilnaid")
    ]
    sys.modules[package_name] = package


class FakeConfigEntry:
    """Minimal config entry type for importing the coordinator."""


class FakeHomeAssistant:
    """Minimal Home Assistant type for importing the coordinator."""


class FakeConfigEntryAuthFailed(Exception):
    """Minimal Home Assistant authentication error."""


class FakeDataUpdateCoordinator[DataT]:
    """Capture coordinator initialization without Home Assistant installed."""

    def __init__(self, *args: Any, update_interval: timedelta, **kwargs: Any) -> None:
        self.update_interval = update_interval


class FakeUpdateFailed(Exception):
    """Minimal Home Assistant update error with retry timing."""

    def __init__(self, *args: Any, retry_after: float | None = None) -> None:
        super().__init__(*args)
        self.retry_after = retry_after


homeassistant = ModuleType("homeassistant")
config_entries = ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = FakeConfigEntry
core = ModuleType("homeassistant.core")
core.HomeAssistant = FakeHomeAssistant
exceptions = ModuleType("homeassistant.exceptions")
exceptions.ConfigEntryAuthFailed = FakeConfigEntryAuthFailed
helpers = ModuleType("homeassistant.helpers")
update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
update_coordinator.DataUpdateCoordinator = FakeDataUpdateCoordinator
update_coordinator.UpdateFailed = FakeUpdateFailed
sys.modules.update(
    {
        "homeassistant": homeassistant,
        "homeassistant.config_entries": config_entries,
        "homeassistant.core": core,
        "homeassistant.exceptions": exceptions,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.update_coordinator": update_coordinator,
    }
)

api = import_module(f"{package_name}.api")
coordinator_module = import_module(f"{package_name}.coordinator")


def _kiln(mode: str, *, online: bool = True):
    updated_at = datetime.now(UTC).isoformat() if online else None
    return api.parse_kiln(
        {"mode": mode, "updatedAt": updated_at},
        {"serialNumber": "GENERIC"},
    )


@pytest.mark.parametrize(
    "kilns",
    [
        [],
        [_kiln("Idle")],
        [_kiln("Not Connected")],
        [_kiln("Firing", online=False)],
        [_kiln("Idle"), _kiln("Error", online=False)],
    ],
)
def test_quiescent_kilns_use_five_minute_interval(kilns) -> None:
    assert coordinator_module.poll_interval(kilns) == timedelta(minutes=5)


@pytest.mark.parametrize(
    "mode",
    ["Firing", "Delay Start", "Delayed Start", "Error", "Complete", "Cooling"],
)
def test_active_and_transitional_modes_use_one_minute_interval(mode: str) -> None:
    kilns = [_kiln("Idle"), _kiln(mode)]

    assert coordinator_module.poll_interval(kilns) == timedelta(minutes=1)


def test_coordinator_passes_rate_limit_delay_to_update_failed() -> None:
    class RateLimitedClient:
        async def async_get_kilns(self):
            raise api.BartlettRateLimitError(137)

    coordinator = coordinator_module.BartlettCoordinator(
        FakeHomeAssistant(), FakeConfigEntry(), RateLimitedClient()
    )

    with pytest.raises(FakeUpdateFailed) as raised:
        asyncio.run(coordinator._async_update_data())

    assert raised.value.retry_after == 137
