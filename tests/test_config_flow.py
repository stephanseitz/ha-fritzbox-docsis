"""Tests for setup, reauthentication and options."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fritzbox_docsis.config_flow import normalize_url
from custom_components.fritzbox_docsis.const import (
    CONF_FETCH_LOG,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DOMAIN,
)

from .mock_fritzbox import PASSWORD, USERNAME


def test_normalize_url() -> None:
    assert normalize_url("192.168.178.1") == "http://192.168.178.1"
    assert normalize_url("abc.myfritz.net:44443") == "https://abc.myfritz.net:44443"
    assert (
        normalize_url("https://abc.myfritz.net:44443/#/cable/channels")
        == "https://abc.myfritz.net:44443"
    )


async def test_user_flow_success(hass: HomeAssistant, fritzbox) -> None:
    _, url = fritzbox
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: url,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_VERIFY_SSL: True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == url
    await hass.async_block_till_done()


async def test_user_flow_invalid_auth(hass: HomeAssistant, fritzbox) -> None:
    _, url = fritzbox
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: "wrong"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, socket_enabled) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://127.0.0.1:1",
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured(hass: HomeAssistant, fritzbox) -> None:
    _, url = fritzbox
    host = url.split("://")[1]
    MockConfigEntry(domain=DOMAIN, unique_id=host, data={CONF_URL: url}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, fritzbox) -> None:
    _, url = fritzbox
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=url.split("://")[1],
        data={CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: "old"},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == PASSWORD
    await hass.async_block_till_done()


async def test_options(hass: HomeAssistant, fritzbox) -> None:
    _, url = fritzbox
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=url.split("://")[1],
        data={CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 120, CONF_FETCH_LOG: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_SCAN_INTERVAL: 120, CONF_FETCH_LOG: False}
    assert entry.runtime_data.update_interval.total_seconds() == 120
