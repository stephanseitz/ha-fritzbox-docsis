"""UI setup (config flow), reauthentication and options."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import FritzAuthError, FritzConnectionError, FritzDataError, FritzDocsisClient
from .const import (
    CONF_FETCH_LOG,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_FETCH_LOG,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Add the scheme and strip paths/fragments (e.g. "/#/cable")."""
    url = url.strip()
    if "://" not in url:
        scheme = "https" if "myfritz.net" in url.lower() else "http"
        url = f"{scheme}://{url}"
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _validate(hass, data: dict[str, Any]) -> tuple[str, int]:
    """Check access and cable data. Returns (error key, channel count)."""
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True))
    client = FritzDocsisClient(
        session, data[CONF_URL], data[CONF_USERNAME], data[CONF_PASSWORD]
    )
    try:
        info, _ = await client.get_docsis()
    except FritzAuthError as err:
        return ("blocked" if err.block_time else "invalid_auth"), 0
    except FritzConnectionError:
        return "cannot_connect", 0
    except FritzDataError:
        return "no_cable_data", 0
    except Exception:
        _LOGGER.exception("Unexpected error during validation")
        return "unknown", 0
    finally:
        await client.logout()
    return "", len(info.downstream) + len(info.upstream)


def _user_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)
            ): bool,
        }
    )


class FritzDocsisConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = normalize_url(user_input[CONF_URL])
            await self.async_set_unique_id(
                urlparse(user_input[CONF_URL]).netloc.lower()
            )
            self._abort_if_unique_id_configured()
            error, _ = await _validate(self.hass, user_input)
            if not error:
                return self.async_create_entry(title=NAME, data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}),
            errors=errors,
            description_placeholders={
                "local_url": "http://192.168.178.1",
                "myfritz_url": "https://xxxxxxxx.myfritz.net:PORT",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            error, _ = await _validate(self.hass, data)
            if not error:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> FritzDocsisOptionsFlow:
        return FritzDocsisOptionsFlow()


class FritzDocsisOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=30,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_FETCH_LOG,
                        default=options.get(CONF_FETCH_LOG, DEFAULT_FETCH_LOG),
                    ): bool,
                }
            ),
        )
