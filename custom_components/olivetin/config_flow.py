"""Config flow for OliveTin."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OliveTinApiClient,
    OliveTinApiError,
    OliveTinAuthError,
    OliveTinConnectionError,
)
from .const import DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OliveTinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the OliveTin URL and login, and check that it lists actions."""

    VERSION = 1

    async def _test(self, data: Mapping[str, Any]) -> dict[str, str]:
        client = OliveTinApiClient(
            async_get_clientsession(self.hass, data[CONF_VERIFY_SSL]),
            data[CONF_URL],
            data.get(CONF_USERNAME) or None,
            data.get(CONF_PASSWORD) or None,
        )
        try:
            await client.get_actions()
        except OliveTinAuthError:
            return {"base": "invalid_auth"}
        except OliveTinConnectionError:
            return {"base": "cannot_connect"}
        except OliveTinApiError:
            return {"base": "invalid_response"}
        except Exception:
            _LOGGER.exception("Unexpected error while testing OliveTin")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            data = {**user_input, CONF_URL: url}
            errors = await self._test(data)
            if not errors:
                return self.async_create_entry(title="OliveTin", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=DEFAULT_URL): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._test({**entry.data, **user_input})
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
