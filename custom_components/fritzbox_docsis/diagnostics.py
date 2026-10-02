"""Diagnostics data (Settings > Devices > … > Download diagnostics)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import FritzDocsisConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, CONF_URL, "sid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FritzDocsisConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    result: dict[str, Any] = {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
    }
    if data is not None:
        result.update(
            {
                "fetched_at": data.fetched_at.isoformat(),
                "channels": data.info.as_dict(),
                "corr_rate": data.corr_rate,
                "noncorr_rate": data.noncorr_rate,
                "log_available": data.log_available,
                "recent_cable_events": [e.as_dict() for e in data.recent_events],
                "raw_docinfo": async_redact_data(data.raw, TO_REDACT),
            }
        )
    return result
