"""Bartlett KilnAid integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BartlettApiClient, RateLimitGate
from .const import CONF_TOKEN, DOMAIN, PLATFORMS
from .coordinator import BartlettCoordinator

type BartlettConfigEntry = ConfigEntry[BartlettCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BartlettConfigEntry) -> bool:
    """Set up Bartlett KilnAid from a config entry."""
    rate_limit_gates: dict[str, RateLimitGate] = hass.data.setdefault(DOMAIN, {})
    client = BartlettApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_TOKEN],
        rate_limit_gates.setdefault(entry.entry_id, RateLimitGate()),
    )
    coordinator = BartlettCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    if not coordinator.data:
        raise ConfigEntryNotReady("No claimed Bartlett kilns found")
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BartlettConfigEntry) -> bool:
    """Unload a Bartlett KilnAid config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
