"""Config flow for Bartlett KilnAid."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BartlettApiClient, BartlettApiError, BartlettAuthError
from .const import CONF_TOKEN, DOMAIN


class BartlettConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure Bartlett KilnAid."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial login step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            try:
                client = await BartlettApiClient.async_authenticate(
                    async_get_clientsession(self.hass),
                    email,
                    user_input[CONF_PASSWORD],
                )
            except BartlettAuthError:
                errors["base"] = "invalid_auth"
            except BartlettApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(email)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_TOKEN: client.token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauthentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication credentials."""
        errors: dict[str, str] = {}
        email = self._reauth_entry.data[CONF_EMAIL]
        if user_input is not None:
            try:
                client = await BartlettApiClient.async_authenticate(
                    async_get_clientsession(self.hass),
                    email,
                    user_input[CONF_PASSWORD],
                )
            except BartlettAuthError:
                errors["base"] = "invalid_auth"
            except BartlettApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates={CONF_TOKEN: client.token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": email},
            errors=errors,
        )
