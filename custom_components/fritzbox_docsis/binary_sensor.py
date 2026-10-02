"""Binary sensor: cable connection in sync yes/no (from the event log)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FritzDocsisConfigEntry, FritzDocsisCoordinator
from .entity import FritzDocsisEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzDocsisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CableSyncBinarySensor(entry.runtime_data)])


class CableSyncBinarySensor(FritzDocsisEntity, BinarySensorEntity):
    """On while the cable modem is synchronised with the network."""

    _attr_translation_key = "cable_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: FritzDocsisCoordinator) -> None:
        super().__init__(coordinator, "cable_sync")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.log_available

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.cable_connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "recent_events": [
                f"{e.timestamp:%d.%m. %H:%M:%S} {e.message}"
                for e in self.coordinator.data.recent_events[:10]
            ]
        }
