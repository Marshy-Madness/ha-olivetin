"""OliveTin integration: a button for every OliveTin action."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import OliveTinApiClient, OliveTinApiError
from .const import DOMAIN
from .coordinator import OliveTinConfigEntry, OliveTinCoordinator, default_arguments

PLATFORMS = [Platform.BUTTON]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_START_ACTION = "start_action"

START_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required("action"): cv.string,
        vol.Optional("arguments", default={}): vol.Schema({cv.string: cv.string}),
    }
)


def _coordinator(hass: HomeAssistant) -> OliveTinCoordinator:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError("No loaded OliveTin config entry")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the start_action service, for actions that take arguments."""

    async def start_action(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass)
        action = coordinator.find(call.data["action"])
        if action is None:
            raise ServiceValidationError(
                f"No OliveTin action matching {call.data['action']!r}"
            )
        arguments = default_arguments(action) | call.data["arguments"]
        try:
            tracking_id = await coordinator.client.start_action(action["id"], arguments)
        except OliveTinApiError as err:
            raise HomeAssistantError(f"OliveTin: {err}") from err
        return {"execution_tracking_id": tracking_id}

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_ACTION,
        start_action,
        START_ACTION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OliveTinConfigEntry) -> bool:
    client = OliveTinApiClient(
        async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
        entry.data[CONF_URL],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )
    coordinator = OliveTinCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OliveTinConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
