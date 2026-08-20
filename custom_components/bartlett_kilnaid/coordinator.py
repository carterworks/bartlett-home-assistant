"""Data coordinator for Bartlett KilnAid."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BartlettApiClient, BartlettApiError, BartlettAuthError, KilnData
from .const import DOMAIN, POLL_INTERVAL

LOGGER = logging.getLogger(__name__)


class BartlettCoordinator(DataUpdateCoordinator[dict[str, KilnData]]):
    """Poll Bartlett's cloud API for all claimed kilns."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: BartlettApiClient,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=POLL_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, KilnData]:
        try:
            return await self.client.async_get_kilns()
        except BartlettAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BartlettApiError as err:
            raise UpdateFailed(str(err)) from err
