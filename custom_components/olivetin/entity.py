"""Base entity for OliveTin."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OliveTinCoordinator


class OliveTinEntity(CoordinatorEntity[OliveTinCoordinator]):
    """All OliveTin entities hang off one device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OliveTinCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="OliveTin",
            manufacturer="OliveTin",
            model="OliveTin",
            configuration_url=entry.data["url"],
        )
