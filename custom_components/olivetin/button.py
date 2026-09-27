"""One button per OliveTin action, kept in sync with OliveTin's config."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import OliveTinApiError
from .coordinator import OliveTinConfigEntry, OliveTinCoordinator, default_arguments
from .entity import OliveTinEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OliveTinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"

    @callback
    def _sync_entities() -> None:
        current = set(coordinator.data)
        new = [OliveTinActionButton(coordinator, key) for key in current - known]
        known.update(current)
        if new:
            async_add_entities(new)

        # Actions removed from OliveTin's config (including while HA was down).
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg_entry.domain != "button" or not reg_entry.unique_id.startswith(prefix):
                continue
            key = reg_entry.unique_id.removeprefix(prefix)
            if key not in current:
                known.discard(key)
                registry.async_remove(reg_entry.entity_id)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class OliveTinActionButton(OliveTinEntity, ButtonEntity):
    """Starts one OliveTin action with its default argument values."""

    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, coordinator: OliveTinCoordinator, key: str) -> None:
        self.key = key
        super().__init__(coordinator, key)
        self._attr_name = coordinator.data[key].get("title") or key

    @property
    def _action(self) -> dict[str, Any] | None:
        return self.coordinator.data.get(self.key)

    @property
    def available(self) -> bool:
        action = self._action
        return super().available and action is not None and action.get("canExec", True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        action = self._action or {}
        return {
            "action_id": action.get("id"),
            "arguments": [arg.get("name") for arg in action.get("arguments") or []],
        }

    async def async_press(self) -> None:
        action = self._action
        if action is None:
            raise HomeAssistantError(f"OliveTin action {self.key} no longer exists")
        try:
            await self.coordinator.client.start_action(
                action["id"], default_arguments(action)
            )
        except OliveTinApiError as err:
            raise HomeAssistantError(f"OliveTin: {err}") from err
