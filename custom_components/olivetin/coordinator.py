"""Polls OliveTin for its list of actions."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .api import OliveTinApiClient, OliveTinApiError, OliveTinAuthError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type OliveTinConfigEntry = ConfigEntry[OliveTinCoordinator]


def default_arguments(action: dict[str, Any]) -> dict[str, str]:
    """Argument values a button press sends: each argument's configured default."""
    return {
        arg["name"]: arg.get("defaultValue", "")
        for arg in action.get("arguments") or []
        if arg.get("name")
    }


class OliveTinCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetches OliveTin actions, keyed by a slug of their title.

    Actions without an explicit `id:` in OliveTin's config get a fresh random
    UUID every time OliveTin starts, so the id can't be used as a stable entity
    key. The title is stable; the id is looked up from the latest poll on press.
    """

    config_entry: OliveTinConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OliveTinConfigEntry, client: OliveTinApiClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            actions = await self.client.get_actions()
        except OliveTinAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except OliveTinApiError as err:
            raise UpdateFailed(str(err)) from err

        by_key: dict[str, dict[str, Any]] = {}
        for action in actions:
            if not action.get("id"):
                continue
            key = slugify(action.get("title") or "") or action["id"]
            if key in by_key:
                _LOGGER.debug("Duplicate OliveTin title %r, keying by id", action.get("title"))
                key = action["id"]
            by_key[key] = action
        return by_key

    def find(self, action: str) -> dict[str, Any] | None:
        """Look up an action by id, title or title slug."""
        data = self.data or {}
        if action in data:
            return data[action]
        for item in data.values():
            if action in (item.get("id"), item.get("title")):
                return item
        return data.get(slugify(action))
