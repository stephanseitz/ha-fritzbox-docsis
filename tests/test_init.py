"""End-to-end tests: entities, error rates, sync events."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.fritzbox_docsis.const import (
    CONF_FETCH_LOG,
    DOMAIN,
    EVENT_SYNC_LOST,
)

from .mock_fritzbox import PASSWORD, USERNAME

PREFIX = "sensor.fritz_box_kabel_"


@pytest.fixture
async def setup(hass: HomeAssistant, fritzbox, freezer: FrozenDateTimeFactory):
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.language = "de"  # entity IDs below are the German ones
    freezer.move_to("2026-10-02T19:49:00+00:00")  # 21:49 local time
    box, url = fritzbox
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=url.split("://")[1],
        data={CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return box, entry


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_entities(hass: HomeAssistant, setup) -> None:
    _, entry = setup
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get(f"{PREFIX}ds_578_mhz_korrigierbare_fehler")
    assert state is not None
    assert state.state == "1063112"
    assert state.attributes["state_class"] == "total_increasing"
    assert state.attributes["channel_id"] == 4

    assert state.attributes["unit_of_measurement"] == "errors"
    assert hass.states.get(f"{PREFIX}ds_578_mhz_pegel").state == "6.5"
    assert hass.states.get(f"{PREFIX}ds_578_mhz_mse").state == "-37.4"
    assert hass.states.get(f"{PREFIX}ds_ofdm_751_861_mhz_mer").state == "36.0"
    assert hass.states.get(f"{PREFIX}us_ofdma_48_65_mhz_pegel").state == "34.8"
    assert hass.states.get(f"{PREFIX}us_ofdma_modulation").state == "256QAM"
    assert hass.states.get(f"{PREFIX}ds_pegel_min").state == "-1.2"
    assert hass.states.get(f"{PREFIX}ds_pegel_max").state == "8.3"
    assert hass.states.get(f"{PREFIX}ds_mse_schlechtester_kanal").state == "-35.8"
    assert hass.states.get(f"{PREFIX}korrigierbare_fehler_gesamt").state == str(
        1063112
        + 85844
        + sum(
            [
                16,
                16,
                37,
                33,
                26,
                11,
                31,
                39,
                31,
                25,
                55,
                28,
                26,
                26,
                12,
                28,
                22,
                24,
                15,
                17,
                18,
                34,
            ]
        )
    )
    # Rates are unknown after the first poll
    assert (
        hass.states.get(f"{PREFIX}ds_578_mhz_korrigierbare_fehler_pro_stunde").state
        == "unknown"
    )

    # From the event log
    assert hass.states.get(f"{PREFIX}sync_verluste_7_tage").state == "3"
    assert hass.states.get(f"{PREFIX}sync_verluste_24_h").state == "1"
    assert hass.states.get(f"{PREFIX}letzter_sync_verlust").state.startswith(
        "2026-10-01T21:52:28"
    )
    assert (
        hass.states.get("binary_sensor.fritz_box_kabel_kabelverbindung").state == "on"
    )
    assert hass.states.get(f"{PREFIX}synchron_seit").state.startswith(
        "2026-10-02T07:46:38"
    )
    down = hass.states.get(f"{PREFIX}sync_rate_empfangen")
    assert float(down.state) == pytest.approx(1126.4)
    assert down.attributes["unit_of_measurement"] == "Mbit/s"
    assert float(hass.states.get(f"{PREFIX}sync_rate_senden").state) == pytest.approx(
        52.48
    )

    registry = er.async_get(hass)
    disabled = registry.async_get(
        f"{PREFIX}ds_578_mhz_nicht_korrigierbare_fehler_pro_stunde"
    )
    assert disabled is not None and disabled.disabled_by is not None


async def test_rates(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    box, _ = setup
    box.corr_offset = 245_000 // 12  # 5 minutes at 245,000/h
    await _tick(hass, freezer, timedelta(minutes=5))

    rate = float(
        hass.states.get(f"{PREFIX}ds_578_mhz_korrigierbare_fehler_pro_stunde").state
    )
    assert rate == pytest.approx(245_000, rel=0.01)
    assert hass.states.get(f"{PREFIX}auffalligster_kanal").state == "578 MHz"
    total_rate = float(
        hass.states.get(f"{PREFIX}korrigierbare_fehler_pro_stunde").state
    )
    assert total_rate == pytest.approx(245_000, rel=0.01)


async def test_sync_lost_event(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    box, _ = setup
    events = async_capture_events(hass, EVENT_SYNC_LOST)

    # History is not reported on the first run
    await _tick(hass, freezer, timedelta(minutes=5))
    assert events == []

    box.add_log(
        "02.10.26",
        "21:57:10",
        "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
    )
    await _tick(hass, freezer, timedelta(minutes=5))

    assert len(events) == 1
    assert events[0].data["timestamp"].startswith("2026-10-02T21:57:10")
    assert (
        hass.states.get("binary_sensor.fritz_box_kabel_kabelverbindung").state == "off"
    )
    assert hass.states.get(f"{PREFIX}sync_verluste_24_h").state == "2"
    event_state = hass.states.get("event.fritz_box_kabel_kabel_synchronisation")
    assert event_state.attributes["event_type"] == "sync_lost"
    assert event_state.attributes["timestamp"].startswith("2026-10-02T21:57:10")

    # Same log again -> no duplicate event
    await _tick(hass, freezer, timedelta(minutes=5))
    assert len(events) == 1


async def test_failed_update_does_not_repeat_event(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    box, _ = setup
    await _tick(hass, freezer, timedelta(minutes=5))
    box.add_log(
        "02.10.26",
        "21:57:10",
        "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
    )
    await _tick(hass, freezer, timedelta(minutes=5))
    event_id = "event.fritz_box_kabel_kabel_synchronisation"
    fired_at = hass.states.get(event_id).state

    # A failed poll hands the previous data to the listeners again
    box.fail_docinfo = True
    await _tick(hass, freezer, timedelta(minutes=5))
    box.fail_docinfo = False
    await _tick(hass, freezer, timedelta(minutes=5))
    assert hass.states.get(event_id).state == fired_at


async def test_counter_reset_without_log(
    hass: HomeAssistant, fritzbox, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.language = "de"
    box, url = fritzbox
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=url.split("://")[1],
        data={CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        options={CONF_FETCH_LOG: False},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_SYNC_LOST)

    box.corr_offset = -1_000_000  # counters went down -> resync
    await _tick(hass, freezer, timedelta(minutes=5))
    assert len(events) == 1
    assert events[0].data["source"] == "counters"
    assert hass.states.get(f"{PREFIX}letzter_sync_verlust").state == "unavailable"
    assert (
        hass.states.get(f"{PREFIX}ds_578_mhz_korrigierbare_fehler_pro_stunde").state
        == "unknown"
    )


async def test_unavailable_and_recovery(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    box, _ = setup
    box.fail_docinfo = True
    await _tick(hass, freezer, timedelta(minutes=5))
    assert hass.states.get(f"{PREFIX}ds_578_mhz_pegel").state == "unavailable"
    box.fail_docinfo = False
    await _tick(hass, freezer, timedelta(minutes=5))
    assert hass.states.get(f"{PREFIX}ds_578_mhz_pegel").state == "6.5"


async def test_unload(hass: HomeAssistant, setup) -> None:
    _, entry = setup
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_diagnostics(hass: HomeAssistant, setup) -> None:
    from custom_components.fritzbox_docsis.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    _, entry = setup
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"][CONF_PASSWORD] == "**REDACTED**"
    assert len(diag["channels"]["downstream"]) == 26


async def test_no_duplicate_events_after_reload(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    box, entry = setup
    events = async_capture_events(hass, EVENT_SYNC_LOST)
    box.add_log(
        "02.10.26",
        "21:57:10",
        "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
    )
    await _tick(hass, freezer, timedelta(minutes=5))
    assert len(events) == 1

    # Reload: the stored state prevents a duplicate event
    await _tick(hass, freezer, timedelta(seconds=5))  # wait for the delayed save
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer, timedelta(minutes=5))
    assert len(events) == 1

    # A genuinely new event is reported
    box.add_log(
        "02.10.26",
        "22:10:00",
        "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
    )
    await _tick(hass, freezer, timedelta(minutes=5))
    assert len(events) == 2


async def test_english_names(
    hass: HomeAssistant, fritzbox, freezer: FrozenDateTimeFactory
) -> None:
    """With an English system language, entity IDs, names and units are English."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.language = "en"
    _, url = fritzbox
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=url.split("://")[1],
        data={CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fritz_box_cable_ds_578_mhz_correctable_errors")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "errors"
    assert state.attributes["friendly_name"] == (
        "FRITZ!Box Cable DS 578 MHz correctable errors"
    )
    assert hass.states.get("sensor.fritz_box_cable_ds_578_mhz_power_level").state == (
        "6.5"
    )
    assert hass.states.get("binary_sensor.fritz_box_cable_cable_connection") is not None
    assert hass.states.get("event.fritz_box_cable_cable_sync") is not None


async def test_sync_rate_kept_when_log_rotates(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    """The sync rate survives the "cable available" entry rotating out of the log."""
    box, _ = setup
    await _tick(hass, freezer, timedelta(seconds=5))  # wait for the delayed save
    box.log = [e for e in box.log if "Kabel-Internet" not in e["msg"]]
    await _tick(hass, freezer, timedelta(minutes=5))
    assert float(hass.states.get(f"{PREFIX}sync_rate_empfangen").state) == (
        pytest.approx(1126.4)
    )

    # After a sync loss there is no valid rate until the next "available" entry
    box.add_log(
        "02.10.26",
        "21:57:10",
        "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
    )
    await _tick(hass, freezer, timedelta(minutes=5))
    assert hass.states.get(f"{PREFIX}sync_rate_empfangen").state == "unknown"

    box.add_log(
        "02.10.26",
        "21:59:00",
        "Kabel-Internet ist verfügbar (Synchronisierung besteht mit 1003000/51200 kbit/s).",
    )
    await _tick(hass, freezer, timedelta(minutes=5))
    assert float(hass.states.get(f"{PREFIX}sync_rate_empfangen").state) == (
        pytest.approx(1003.0)
    )


async def test_log_timestamp_jitter_no_duplicate_events(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    """The box reports the same entry one second apart -> no new event, stable time."""
    box, entry = setup
    events = async_capture_events(hass, "fritzbox_docsis_sync_restored")
    since = hass.states.get(f"{PREFIX}synchron_seit").state

    def shift(seconds: int) -> None:
        for item in box.log:
            if "verfügbar" in item["msg"]:
                item["time"] = f"09:46:{38 + seconds:02d}"

    for seconds in (1, 0, 1, 0):
        shift(seconds)
        await _tick(hass, freezer, timedelta(minutes=5))
    assert events == []
    assert hass.states.get(f"{PREFIX}synchron_seit").state == since

    # Also stable across a reload (known timestamps are persisted)
    await _tick(hass, freezer, timedelta(seconds=5))
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    shift(1)
    await _tick(hass, freezer, timedelta(minutes=5))
    assert events == []
    assert hass.states.get(f"{PREFIX}synchron_seit").state == since
