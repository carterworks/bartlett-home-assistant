"""Sensors for Bartlett KilnAid."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BartlettConfigEntry
from .api import KilnData
from .entity import BartlettEntity


@dataclass(frozen=True, slots=True)
class SensorDefinition:
    """Describe a Bartlett sensor."""

    key: str
    name: str
    value: Callable[[KilnData], Any]
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    unit: str | None = None


SENSORS = (
    SensorDefinition("mode", "Mode", lambda kiln: kiln.mode),
    SensorDefinition("program", "Program", lambda kiln: kiln.program),
    SensorDefinition("segment", "Segment", lambda kiln: kiln.segment),
    SensorDefinition(
        "set_point",
        "Set point",
        lambda kiln: kiln.set_point,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
    ),
    SensorDefinition(
        "firing_time",
        "Firing time",
        lambda kiln: kiln.firing_minutes,
        SensorDeviceClass.DURATION,
        unit=UnitOfTime.MINUTES,
    ),
    SensorDefinition(
        "hold_remaining",
        "Hold remaining",
        lambda kiln: kiln.hold_minutes,
        SensorDeviceClass.DURATION,
        unit=UnitOfTime.MINUTES,
    ),
    SensorDefinition(
        "total_firings",
        "Total firings",
        lambda kiln: kiln.total_firings,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorDefinition(
        "last_update",
        "Last update",
        lambda kiln: kiln.updated_at,
        SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BartlettConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for every claimed kiln."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for serial, kiln in coordinator.data.items():
        entities.extend(
            BartlettKilnSensor(coordinator, serial, definition)
            for definition in SENSORS
        )
        if kiln.number_of_zones == 1:
            entities.append(BartlettTemperatureSensor(coordinator, serial, 2, None))
        else:
            entities.extend(
                BartlettTemperatureSensor(coordinator, serial, zone, zone)
                for zone in range(1, kiln.number_of_zones + 1)
            )
    async_add_entities(entities)


class BartlettKilnSensor(BartlettEntity, SensorEntity):
    """A scalar kiln sensor."""

    def __init__(
        self,
        coordinator,
        serial: str,
        definition: SensorDefinition,
    ) -> None:
        super().__init__(coordinator, serial)
        self.definition = definition
        self._attr_unique_id = f"{serial}_{definition.key}"
        self._attr_name = definition.name
        self._attr_device_class = definition.device_class
        self._attr_state_class = definition.state_class
        self._attr_native_unit_of_measurement = definition.unit

    @property
    def available(self) -> bool:
        """Return whether this kiln has reported recently."""
        return super().available and self.kiln.online

    @property
    def native_value(self):
        """Return the current sensor value."""
        return self.definition.value(self.kiln)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return a dynamic temperature unit where needed."""
        if self.definition.device_class == SensorDeviceClass.TEMPERATURE:
            return (
                UnitOfTemperature.CELSIUS
                if self.kiln.temperature_scale == "C"
                else UnitOfTemperature.FAHRENHEIT
            )
        return self.definition.unit


class BartlettTemperatureSensor(BartlettEntity, SensorEntity):
    """A thermocouple temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator, serial: str, source_zone: int, display_zone: int | None
    ) -> None:
        super().__init__(coordinator, serial)
        key = "temperature" if display_zone is None else f"temperature_{display_zone}"
        self.source_zone = source_zone
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_name = (
            "Temperature"
            if display_zone is None
            else f"Temperature zone {display_zone}"
        )

    @property
    def available(self) -> bool:
        """Return whether this kiln has reported recently."""
        return super().available and self.kiln.online

    @property
    def native_value(self) -> float | None:
        """Return the thermocouple temperature."""
        return self.kiln.zone_temperatures[self.source_zone - 1]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the kiln's configured temperature scale."""
        return (
            UnitOfTemperature.CELSIUS
            if self.kiln.temperature_scale == "C"
            else UnitOfTemperature.FAHRENHEIT
        )
