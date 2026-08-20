"""Base entity for Bartlett KilnAid."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BartlettCoordinator


class BartlettEntity(CoordinatorEntity[BartlettCoordinator]):
    """Base entity tied to one kiln."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BartlettCoordinator, serial: str) -> None:
        super().__init__(coordinator)
        self.serial = serial

    @property
    def kiln(self):
        """Return the latest kiln data."""
        return self.coordinator.data[self.serial]

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the kiln controller."""
        kiln = self.kiln
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=kiln.name,
            manufacturer="Bartlett Instrument Company",
            model="Genesis",
            serial_number=self.serial,
            sw_version=kiln.firmware,
            configuration_url="https://kilnaid.bartinst.com/",
        )
