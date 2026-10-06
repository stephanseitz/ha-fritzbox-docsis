"""Parser for FRITZ!Box cable data (no Home Assistant dependencies).

The FRITZ!Box serves the values of the "Internet > Cable Information" page as JSON via
``data.lua?page=docInfo``. The field names have changed slightly several times between
FRITZ!OS versions (e.g. ``type`` -> ``modulation``), so parsing is deliberately
lenient.

This module is used both by the integration and by the check script
``tools/fritz_docsis_check.py`` and must therefore only use the standard library.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import re
from typing import Any

# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class DownstreamChannel:
    """A downstream channel (receive direction)."""

    key: str  # stable key, e.g. "ds30_5780" (frequency in 100 kHz)
    docsis: str  # "3.0" or "3.1"
    channel_id: int | None
    frequency_mhz: float | None  # center frequency (3.0) or start frequency (3.1)
    frequency_end_mhz: float | None  # 3.1 only (OFDM block)
    label: str  # e.g. "578 MHz" or "135–325 MHz"
    power_dbmv: float | None
    modulation: str | None
    mse_db: float | None = None  # DOCSIS 3.0 only
    mer_db: float | None = None  # DOCSIS 3.1 only
    latency_ms: float | None = None
    corr_errors: int | None = None
    noncorr_errors: int | None = None
    plc_mhz: float | None = None
    fft: str | None = None


@dataclass(slots=True)
class UpstreamChannel:
    """An upstream channel (transmit direction)."""

    key: str
    docsis: str
    channel_id: int | None
    frequency_mhz: float | None
    frequency_end_mhz: float | None
    label: str
    power_dbmv: float | None
    modulation: str | None
    multiplex: str | None = None
    active_subcarriers: int | None = None
    fft: str | None = None


@dataclass(slots=True)
class DocsisInfo:
    """All channels from one query."""

    downstream: dict[str, DownstreamChannel] = field(default_factory=dict)
    upstream: dict[str, UpstreamChannel] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "downstream": [asdict(c) for c in self.downstream.values()],
            "upstream": [asdict(c) for c in self.upstream.values()],
        }


@dataclass(slots=True)
class LogEntry:
    """An entry from the FRITZ!Box event log."""

    timestamp: datetime  # naive, FRITZ!Box local time
    message: str
    group: str | None = None
    msg_id: int | None = None


# Categories of cable events in the event log
CABLE_SYNC_LOST = "sync_lost"
CABLE_SYNC_START = "sync_start"
CABLE_SYNC_OK = "sync_ok"

_CABLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (CABLE_SYNC_LOST, re.compile(r"kabel-internet antwortet nicht", re.IGNORECASE)),
    (
        CABLE_SYNC_START,
        re.compile(r"kabel-internet synchronisierung beginnt", re.IGNORECASE),
    ),
    (CABLE_SYNC_OK, re.compile(r"kabel-internet ist verf[üu]gbar", re.IGNORECASE)),
    # English UI (wording not verified, hence deliberately loose)
    (
        CABLE_SYNC_LOST,
        re.compile(r"cable.*(not respond|no synchroni)", re.IGNORECASE),
    ),
    (
        CABLE_SYNC_OK,
        re.compile(r"cable.*(is available|synchronized with)", re.IGNORECASE),
    ),
)


_SYNC_RATE_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*kbit/s", re.IGNORECASE)


def parse_sync_rate(message: str) -> tuple[int, int] | None:
    """Extract the sync rate (down, up) in kbit/s from a "cable available" message.

    Example: "Kabel-Internet ist verfügbar (Synchronisierung besteht mit
    1126400/52480 kbit/s)." -> (1126400, 52480)
    """
    match = _SYNC_RATE_RE.search(message)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def classify_cable_event(message: str) -> str | None:
    """Map a log message to a cable event kind (or None)."""
    for kind, pattern in _CABLE_PATTERNS:
        if pattern.search(message):
            return kind
    return None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _num(value: Any) -> float | None:
    """Convert numbers and numeric strings ("6.5", "-37,4 dB", 12) to float."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUM_RE.search(str(value))
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def _int(value: Any) -> int | None:
    number = _num(value)
    return None if number is None else round(number)


def _first(channel: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in channel and channel[key] not in (None, ""):
            return channel[key]
    return None


def _frequency(value: Any) -> tuple[float | None, float | None]:
    """Parse "578.000", 578 or "134.975 - 324.975" -> (start, end)."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    numbers = [float(n.replace(",", ".")) for n in _NUM_RE.findall(str(value))]
    # "134.975 - 324.975": the hyphen must not count as a minus sign of the 2nd number
    numbers = [abs(n) for n in numbers]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], None
    return numbers[0], numbers[1]


def _fmt_mhz(value: float) -> str:
    # Round to 0.1 MHz: the box reports e.g. 37.200 one time and 37.201 MHz the next
    # Dot as decimal separator like in the FRITZ!Box UI (gives clean entity IDs)
    return f"{round(value, 1):.1f}".rstrip("0").rstrip(".")


def _label(start: float | None, end: float | None) -> str:
    if start is None:
        return "unknown"
    if end is None:
        return f"{_fmt_mhz(start)} MHz"
    return f"{_fmt_mhz(round(start))}–{_fmt_mhz(round(end))} MHz"


def _key(prefix: str, start: float | None, channel_id: int | None, index: int) -> str:
    if start is not None:
        # Key in 100 kHz steps so that small fluctuations in the reported
        # frequency (37.200 / 37.201 MHz) do not create new entities
        return f"{prefix}_{round(start * 10)}"
    if channel_id is not None:
        return f"{prefix}_id{channel_id}"
    return f"{prefix}_idx{index}"


def _modulation(channel: dict[str, Any]) -> str | None:
    value = _first(channel, "modulation", "type", "mod", "qam")
    return None if value is None else str(value)


# --------------------------------------------------------------------------- #
# docInfo
# --------------------------------------------------------------------------- #


def _section(data: dict[str, Any], *names: str) -> dict[str, Any]:
    for name in names:
        value = data.get(name)
        if isinstance(value, dict):
            return value
    return {}


def _channels(section: dict[str, Any], version: str) -> list[dict[str, Any]]:
    value = section.get(version)
    if isinstance(value, list):
        return [c for c in value if isinstance(c, dict)]
    return []


def parse_docinfo(payload: dict[str, Any]) -> DocsisInfo:
    """Parse the JSON response of ``data.lua?page=docInfo``.

    Expected structure (FRITZ!OS 7.x/8.x)::

        {"data": {"channelDs": {"docsis30": [...], "docsis31": [...]},
                  "channelUs": {"docsis30": [...], "docsis31": [...]}}}
    """
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise ValueError("Response contains no data block")

    ds_section = _section(data, "channelDs", "channelsDs", "downstream")
    us_section = _section(data, "channelUs", "channelsUs", "upstream")
    if not ds_section and not us_section:
        raise ValueError(
            "No cable channels in the response (not a FRITZ!Box Cable or missing permissions?)"
        )

    info = DocsisInfo()

    for version, docsis in (("docsis30", "3.0"), ("docsis31", "3.1")):
        for index, ch in enumerate(_channels(ds_section, version)):
            channel_id = _int(_first(ch, "channelID", "channelId", "id"))
            start, end = _frequency(_first(ch, "frequency", "freq"))
            prefix = "ds30" if docsis == "3.0" else "ds31"
            key = _key(prefix, start, channel_id, index)
            info.downstream[key] = DownstreamChannel(
                key=key,
                docsis=docsis,
                channel_id=channel_id,
                frequency_mhz=start,
                frequency_end_mhz=end,
                label=_label(start, end),
                power_dbmv=_num(_first(ch, "powerLevel", "power", "level")),
                modulation=_modulation(ch),
                mse_db=_num(_first(ch, "mse", "snr")) if docsis == "3.0" else None,
                mer_db=_num(_first(ch, "mer", "snr")) if docsis == "3.1" else None,
                latency_ms=_num(_first(ch, "latency")),
                corr_errors=_int(
                    _first(ch, "corrErrors", "correctedErrors", "corrected")
                ),
                noncorr_errors=_int(
                    _first(ch, "nonCorrErrors", "uncorrectedErrors", "uncorrectable")
                ),
                plc_mhz=_num(_first(ch, "plc")),
                fft=None if _first(ch, "fft") is None else str(_first(ch, "fft")),
            )

        for index, ch in enumerate(_channels(us_section, version)):
            channel_id = _int(_first(ch, "channelID", "channelId", "id"))
            start, end = _frequency(_first(ch, "frequency", "freq"))
            prefix = "us30" if docsis == "3.0" else "us31"
            key = _key(prefix, start, channel_id, index)
            info.upstream[key] = UpstreamChannel(
                key=key,
                docsis=docsis,
                channel_id=channel_id,
                frequency_mhz=start,
                frequency_end_mhz=end,
                label=_label(start, end),
                power_dbmv=_num(_first(ch, "powerLevel", "power", "level")),
                modulation=_modulation(ch),
                multiplex=None
                if _first(ch, "multiplex") is None
                else str(_first(ch, "multiplex")),
                active_subcarriers=_int(_first(ch, "activesub", "activeSubcarriers")),
                fft=None if _first(ch, "fft") is None else str(_first(ch, "fft")),
            )

    return info


# --------------------------------------------------------------------------- #
# Event log
# --------------------------------------------------------------------------- #

_DATE_FORMATS = ("%d.%m.%y %H:%M:%S", "%d.%m.%Y %H:%M:%S")


def _parse_ts(date: str, time: str) -> datetime | None:
    text = f"{date.strip()} {time.strip()}"
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)  # noqa: DTZ007 (box local time)
        except ValueError:
            continue
    return None


def parse_log(payload: dict[str, Any]) -> list[LogEntry]:
    """Parse the response of ``data.lua?page=log``.

    Newer FRITZ!OS versions return objects ``{"date", "time", "msg", "group", "id"}``,
    older ones lists ``[date, time, message, id, group, ...]``. Both are supported.
    Returns the newest entries first.
    """
    data = payload.get("data", payload)
    raw = data.get("log") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise ValueError("Response contains no event log")

    entries: list[LogEntry] = []
    for item in raw:
        date = time = msg = group = None
        msg_id = None
        if isinstance(item, dict):
            date, time = item.get("date"), item.get("time")
            msg = item.get("msg") or item.get("message") or item.get("text")
            group = item.get("group")
            msg_id = _int(item.get("id"))
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            date, time, msg = item[0], item[1], item[2]
            msg_id = _int(item[3]) if len(item) > 3 else None
            group = str(item[4]) if len(item) > 4 else None
        if not (date and time and msg):
            continue
        ts = _parse_ts(str(date), str(time))
        if ts is None:
            continue
        entries.append(
            LogEntry(timestamp=ts, message=str(msg), group=group, msg_id=msg_id)
        )

    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries
