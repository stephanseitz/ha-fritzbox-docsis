"""Constants for the FRITZ!Box Cable (DOCSIS) integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "fritzbox_docsis"
NAME: Final = "FRITZ!Box Cable (DOCSIS)"

CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_FETCH_LOG: Final = "fetch_log"

DEFAULT_SCAN_INTERVAL: Final = 300  # seconds
MIN_SCAN_INTERVAL: Final = 60
MAX_SCAN_INTERVAL: Final = 3600
DEFAULT_FETCH_LOG: Final = True

# Events on the HA bus (for automations)
EVENT_SYNC_LOST: Final = f"{DOMAIN}_sync_lost"
EVENT_SYNC_RESTORED: Final = f"{DOMAIN}_sync_restored"

STORAGE_VERSION: Final = 1

INVALID_SID: Final = "0000000000000000"
