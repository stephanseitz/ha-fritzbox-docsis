"""Tests for the parser (no network)."""

from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.fritzbox_docsis.parser import (
    CABLE_SYNC_LOST,
    CABLE_SYNC_OK,
    CABLE_SYNC_START,
    classify_cable_event,
    parse_docinfo,
    parse_log,
    parse_sync_rate,
)

from .mock_fritzbox import BASE_LOG, docinfo_payload


@pytest.mark.parametrize("style", ["new", "old"])
def test_parse_docinfo(style: str) -> None:
    info = parse_docinfo(docinfo_payload("abc", field_style=style))

    assert len(info.downstream) == 26
    assert len(info.upstream) == 4

    ch = info.downstream["ds30_5780"]
    assert ch.docsis == "3.0"
    assert ch.channel_id == 4
    assert ch.label == "578 MHz"
    assert ch.power_dbmv == 6.5
    assert ch.mse_db == -37.4
    assert ch.corr_errors == 1063112
    assert ch.noncorr_errors == 0
    assert ch.modulation == "256QAM"

    ofdm = info.downstream["ds31_7510"]
    assert ofdm.docsis == "3.1"
    assert ofdm.frequency_mhz == 750.975
    assert ofdm.frequency_end_mhz == 860.975
    assert ofdm.label == "751–861 MHz"
    assert ofdm.mer_db == 36
    assert ofdm.noncorr_errors == 61
    assert ofdm.corr_errors is None

    ofdma = info.upstream["us31_480"]
    assert ofdma.modulation == "256QAM"
    assert ofdma.active_subcarriers == 320
    assert ofdma.label == "48–65 MHz"

    us = info.upstream["us30_308"]
    assert us.power_dbmv == 41.8
    assert us.label == "30.8 MHz"
    assert us.multiplex == "ATDMA"


def test_parse_docinfo_without_channels() -> None:
    with pytest.raises(ValueError):
        parse_docinfo({"data": {}})


def test_frequency_without_spaces() -> None:
    payload = {
        "data": {
            "channelDs": {
                "docsis31": [
                    {
                        "channelID": 1,
                        "frequency": "134.975-324.975",
                        "powerLevel": 3,
                        "mer": 39,
                    }
                ]
            }
        }
    }
    ch = parse_docinfo(payload).downstream["ds31_1350"]
    assert ch.frequency_end_mhz == 324.975


def test_frequency_jitter_same_key() -> None:
    a = parse_docinfo({"data": {"channelUs": {"docsis30": [{"frequency": "37.200"}]}}})
    b = parse_docinfo({"data": {"channelUs": {"docsis30": [{"frequency": "37.201"}]}}})
    assert list(a.upstream) == list(b.upstream) == ["us30_372"]


def test_parse_log_dicts() -> None:
    entries = parse_log({"data": {"log": BASE_LOG}})
    # Log timestamps are naive (FRITZ!Box local time)
    assert entries[0].timestamp == datetime(2026, 10, 2, 9, 46, 41)
    assert entries[-1].timestamp == datetime(2026, 9, 29, 11, 17, 57)
    kinds = [classify_cable_event(e.message) for e in entries]
    assert kinds.count(CABLE_SYNC_LOST) == 3
    assert kinds.count(CABLE_SYNC_OK) == 1
    assert kinds.count(CABLE_SYNC_START) == 1


def test_parse_log_lists() -> None:
    raw = [[e["date"], e["time"], e["msg"], e["id"], e["group"]] for e in BASE_LOG]
    entries = parse_log({"data": {"log": raw}})
    assert len(entries) == len(BASE_LOG)
    assert entries[0].msg_id == 23


def test_classify_negative() -> None:
    assert classify_cable_event("Internetverbindung wurde getrennt.") is None


def test_parse_sync_rate() -> None:
    assert parse_sync_rate(
        "Kabel-Internet ist verfügbar (Synchronisierung besteht mit 1126400/52480 kbit/s)."
    ) == (1126400, 52480)
    assert parse_sync_rate(
        "Cable internet is available (synchronized with 1126400 / 52480 kbit/s)."
    ) == (1126400, 52480)
    assert parse_sync_rate("Kabel-Internet ist verfügbar.") is None
