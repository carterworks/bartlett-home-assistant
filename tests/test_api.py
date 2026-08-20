"""Tests for Bartlett KilnAid response parsing."""

import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from types import ModuleType

# Load the pure API module without importing the Home Assistant integration runtime.
package = ModuleType("custom_components.bartlett_kilnaid")
package.__path__ = [
    str(Path(__file__).parents[1] / "custom_components" / "bartlett_kilnaid")
]
sys.modules[package.__name__] = package
parse_kiln = import_module("custom_components.bartlett_kilnaid.api").parse_kiln


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
            "firmwareVersion": "LT4-4.22.0",
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
