"""Binary sensors for Bartlett KilnAid."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BartlettConfigEntry
from .entity import BartlettEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BartlettConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up status sensors for every claimed kiln."""
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for serial in coordinator.data
        for entity in (
            BartlettConnectivitySensor(coordinator, serial),
            BartlettAlarmSensor(coordinator, serial),
            BartlettErrorSensor(coordinator, serial),
        )
    )


class BartlettConnectivitySensor(BartlettEntity, BinarySensorEntity):
    """Whether the controller has reported recently."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Connectivity"

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_connectivity"

    @property
    def is_on(self) -> bool:
        return self.kiln.online


class BartlettAlarmSensor(BartlettEntity, BinarySensorEntity):
    """Whether the controller reports an alarm."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Alarm"

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_alarm"

    @property
    def available(self) -> bool:
        return super().available and self.kiln.online

    @property
    def is_on(self) -> bool:
        return self.kiln.alarm not in (None, "", "OFF")

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"alarm_code": self.kiln.alarm}


class BartlettErrorSensor(BartlettEntity, BinarySensorEntity):
    """Whether the controller is in an error mode."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Error"

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_error"

    @property
    def available(self) -> bool:
        return super().available and self.kiln.online

    @property
    def is_on(self) -> bool:
        return self.kiln.mode == "Error"

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        return {
            "error_number": self.kiln.error_number,
            "error_text": self.kiln.error_text,
        }
