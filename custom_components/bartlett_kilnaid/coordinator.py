"""Data coordinator for Bartlett KilnAid."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    BartlettApiClient,
    BartlettApiError,
    BartlettAuthError,
    BartlettRateLimitError,
    KilnData,
)
from .const import ACTIVE_POLL_INTERVAL, DOMAIN, IDLE_POLL_INTERVAL

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
            update_interval=IDLE_POLL_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, KilnData]:
        try:
            kilns = await self.client.async_get_kilns()
        except BartlettAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BartlettRateLimitError as err:
            raise UpdateFailed(str(err), retry_after=err.retry_after) from err
        except BartlettApiError as err:
            raise UpdateFailed(str(err)) from err
        self.update_interval = poll_interval(kilns.values())
        return kilns


def poll_interval(kilns: Iterable[KilnData]) -> timedelta:
    """Select an account polling interval from the current kiln states."""
    if all(
        not kiln.online or kiln.mode.strip().casefold() in {"idle", "not connected"}
        for kiln in kilns
    ):
        return IDLE_POLL_INTERVAL
    return ACTIVE_POLL_INTERVAL
