"""Shared base class for all entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FritzDocsisCoordinator


class FritzDocsisEntity(CoordinatorEntity[FritzDocsisCoordinator]):
    """Base class: one device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FritzDocsisCoordinator, unique_suffix: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            translation_key="fritzbox_cable",
            manufacturer="AVM",
            model="FRITZ!Box Cable",
            configuration_url=coordinator.client.url,
        )
