"""Event entity: every resync shows up in the logbook and can trigger automations."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FritzDocsisConfigEntry, FritzDocsisCoordinator
from .entity import FritzDocsisEntity
from .parser import CABLE_SYNC_LOST, CABLE_SYNC_OK, CABLE_SYNC_START

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzDocsisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CableSyncEvent(entry.runtime_data)])


class CableSyncEvent(FritzDocsisEntity, EventEntity):
    """Fires sync_lost / sync_start / sync_ok with the time from the FRITZ!Box log."""

    _attr_translation_key = "cable_sync"
    _attr_event_types = [CABLE_SYNC_LOST, CABLE_SYNC_START, CABLE_SYNC_OK]
    _attr_icon = "mdi:cable-data"

    def __init__(self, coordinator: FritzDocsisCoordinator) -> None:
        super().__init__(coordinator, "cable_sync_event")

    @callback
    def _handle_coordinator_update(self) -> None:
        new_events = self.coordinator.data.new_events
        if not new_events:
            # only refresh availability
            self.async_write_ha_state()
            return
        for event in new_events:
            self._trigger_event(
                event.kind,
                {
                    "timestamp": event.timestamp.isoformat(),
                    "message": event.message,
                    "source": event.source,
                },
            )
            self.async_write_ha_state()
