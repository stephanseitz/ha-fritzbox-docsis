"""DataUpdateCoordinator: polls the FRITZ!Box periodically and evaluates the data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    FritzAuthError,
    FritzConnectionError,
    FritzDataError,
    FritzDocsisClient,
    FritzError,
)
from .const import (
    CONF_FETCH_LOG,
    CONF_SCAN_INTERVAL,
    DEFAULT_FETCH_LOG,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_SYNC_LOST,
    EVENT_SYNC_RESTORED,
    STORAGE_VERSION,
)
from .parser import (
    CABLE_SYNC_LOST,
    CABLE_SYNC_OK,
    DocsisInfo,
    LogEntry,
    classify_cable_event,
    parse_sync_rate,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CableEvent:
    """A cable event from the log (or derived from a counter reset)."""

    kind: str  # sync_lost | sync_start | sync_ok
    timestamp: datetime  # timezone-aware
    message: str
    source: str = "log"  # log | counters

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "source": self.source,
        }


@dataclass(slots=True)
class DocsisData:
    """Result of one query including derived values."""

    info: DocsisInfo
    raw: dict[str, Any]
    fetched_at: datetime
    corr_rate: dict[str, float | None] = field(
        default_factory=dict
    )  # errors/h per DS channel
    noncorr_rate: dict[str, float | None] = field(default_factory=dict)
    total_corr: int = 0
    total_noncorr: int = 0
    total_corr_rate: float | None = None
    total_noncorr_rate: float | None = None
    counters_reset: bool = False
    log_available: bool = False
    cable_connected: bool | None = None
    last_sync_lost: datetime | None = None
    connected_since: datetime | None = None
    sync_losses_24h: int | None = None
    sync_losses_7d: int | None = None
    sync_rate_down: int | None = None  # kbit/s, from the last "cable available" entry
    sync_rate_up: int | None = None
    recent_events: list[CableEvent] = field(default_factory=list)
    new_events: list[CableEvent] = field(default_factory=list)


type FritzDocsisConfigEntry = ConfigEntry[FritzDocsisCoordinator]


class FritzDocsisCoordinator(DataUpdateCoordinator[DocsisData]):
    """Coordinates the queries."""

    config_entry: FritzDocsisConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FritzDocsisConfigEntry,
        client: FritzDocsisClient,
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._stored: dict[str, Any] | None = None
        self._prev_counters: dict[str, tuple[int | None, int | None]] = {}
        self._prev_totals: tuple[int, int] | None = None
        self._prev_ts: datetime | None = None

    @property
    def fetch_log(self) -> bool:
        return self.config_entry.options.get(CONF_FETCH_LOG, DEFAULT_FETCH_LOG)

    async def _async_setup(self) -> None:
        self._stored = await self._store.async_load() or {}

    # ------------------------------------------------------------------ #

    async def _async_update_data(self) -> DocsisData:
        try:
            info, raw = await self.client.get_docsis()
        except FritzAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (FritzConnectionError, FritzDataError) as err:
            raise UpdateFailed(str(err)) from err

        now = dt_util.utcnow()
        data = DocsisData(info=info, raw=raw, fetched_at=now)
        self._compute_rates(data, now)

        if self.fetch_log:
            try:
                log = await self.client.get_log()
            except FritzAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except FritzError as err:
                _LOGGER.debug("Event log not available: %s", err)
            else:
                data.log_available = True
                self._evaluate_log(data, log, now)

        if not data.log_available and data.counters_reset:
            # Without the log: a counter reset indicates a resync
            data.new_events.append(
                CableEvent(
                    kind=CABLE_SYNC_LOST,
                    timestamp=now,
                    message="Error counters reset – probably a resync",
                    source="counters",
                )
            )

        for event in sorted(data.new_events, key=lambda e: e.timestamp):
            if event.kind == CABLE_SYNC_LOST:
                self.hass.bus.async_fire(EVENT_SYNC_LOST, event.as_dict())
            elif event.kind == CABLE_SYNC_OK:
                self.hass.bus.async_fire(EVENT_SYNC_RESTORED, event.as_dict())

        return data

    # ------------------------------------------------------------------ #

    def _compute_rates(self, data: DocsisData, now: datetime) -> None:
        info = data.info
        total_corr = sum(c.corr_errors or 0 for c in info.downstream.values())
        total_noncorr = sum(c.noncorr_errors or 0 for c in info.downstream.values())
        data.total_corr, data.total_noncorr = total_corr, total_noncorr

        hours = None
        if self._prev_ts is not None:
            elapsed = (now - self._prev_ts).total_seconds()
            if elapsed >= 1:
                hours = elapsed / 3600

        def rate(cur: int | None, prev: int | None) -> float | None:
            if hours is None or cur is None or prev is None or cur < prev:
                return None
            return round((cur - prev) / hours, 1)

        for key, ch in info.downstream.items():
            prev_corr, prev_noncorr = self._prev_counters.get(key, (None, None))
            data.corr_rate[key] = rate(ch.corr_errors, prev_corr)
            data.noncorr_rate[key] = rate(ch.noncorr_errors, prev_noncorr)
            if (
                ch.corr_errors is not None
                and prev_corr is not None
                and ch.corr_errors < prev_corr
            ) or (
                ch.noncorr_errors is not None
                and prev_noncorr is not None
                and ch.noncorr_errors < prev_noncorr
            ):
                data.counters_reset = True

        if self._prev_totals is not None:
            data.total_corr_rate = rate(total_corr, self._prev_totals[0])
            data.total_noncorr_rate = rate(total_noncorr, self._prev_totals[1])
            if (
                total_corr < self._prev_totals[0]
                or total_noncorr < self._prev_totals[1]
            ):
                data.counters_reset = True

        self._prev_counters = {
            key: (ch.corr_errors, ch.noncorr_errors)
            for key, ch in info.downstream.items()
        }
        self._prev_totals = (total_corr, total_noncorr)
        self._prev_ts = now

    def _evaluate_log(
        self, data: DocsisData, log: list[LogEntry], now: datetime
    ) -> None:
        tz = dt_util.get_default_time_zone()
        events: list[CableEvent] = []
        for entry in log:  # newest first
            kind = classify_cable_event(entry.message)
            if kind is None:
                continue
            events.append(
                CableEvent(
                    kind=kind,
                    timestamp=entry.timestamp.replace(tzinfo=tz),
                    message=entry.message,
                )
            )

        data.recent_events = events[:20]
        losses = [e for e in events if e.kind == CABLE_SYNC_LOST]
        data.last_sync_lost = losses[0].timestamp if losses else None
        data.sync_losses_24h = sum(
            1 for e in losses if now - e.timestamp <= timedelta(hours=24)
        )
        data.sync_losses_7d = sum(
            1 for e in losses if now - e.timestamp <= timedelta(days=7)
        )

        latest = events[0] if events else None
        if latest is None:
            data.cable_connected = True
        else:
            data.cable_connected = latest.kind == CABLE_SYNC_OK
            if latest.kind == CABLE_SYNC_OK:
                data.connected_since = latest.timestamp
        if latest is None or latest.kind != CABLE_SYNC_OK:
            data.connected_since = None

        stored = self._stored if self._stored is not None else {}
        new_stored = dict(stored)

        # Sync rate: from the newest "cable available" entry. If the entry has
        # rotated out of the log (long uptime), keep the last known value.
        rate: tuple[int, int] | None = None
        if latest is not None and latest.kind == CABLE_SYNC_OK:
            rate = parse_sync_rate(latest.message)
            if rate is not None:
                new_stored["sync_rate"] = list(rate)
            else:
                new_stored.pop("sync_rate", None)
        elif latest is None:
            saved = stored.get("sync_rate")
            if isinstance(saved, list) and len(saved) == 2:
                rate = (int(saved[0]), int(saved[1]))
        else:
            new_stored.pop("sync_rate", None)
        if rate is not None:
            data.sync_rate_down, data.sync_rate_up = rate

        # Determine new events since the last run (persisted across restarts)
        last_iso: str | None = stored.get("last_event_ts")
        seen_at_last: list[str] = stored.get("seen_at_last", [])

        if events:
            newest = events[0].timestamp
            if last_iso is None:
                # First run: do not report the history as new events
                new: list[CableEvent] = []
            else:
                last_ts = datetime.fromisoformat(last_iso)
                new = [
                    e
                    for e in events
                    if e.timestamp > last_ts
                    or (e.timestamp == last_ts and e.message not in seen_at_last)
                ]
            data.new_events.extend(sorted(new, key=lambda e: e.timestamp))

            new_stored["last_event_ts"] = newest.isoformat()
            new_stored["seen_at_last"] = [
                e.message for e in events if e.timestamp == newest
            ]

        if new_stored != self._stored:
            self._stored = new_stored
            # Delayed save; Store is guaranteed to flush when HA shuts down
            self._store.async_delay_save(lambda: new_stored, 2)
