"""The example dashboards and automations must only reference entities that exist."""

from __future__ import annotations

from pathlib import Path
import re

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import yaml

from custom_components.fritzbox_docsis.const import DOMAIN

from .mock_fritzbox import PASSWORD, USERNAME

EXAMPLES = Path(__file__).parent.parent / "examples"
ENTITY_RE = re.compile(r"\b(?:sensor|binary_sensor|event)\.fritz_box_\w+")


@pytest.mark.parametrize("language", ["de", "en"])
async def test_example_entity_ids_exist(
    hass: HomeAssistant, fritzbox, language: str
) -> None:
    hass.config.language = language
    _, url = fritzbox
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=url.split("://")[1],
        data={CONF_URL: url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    files = sorted((EXAMPLES / language).glob("*.yaml"))
    assert files
    for file in files:
        text = file.read_text(encoding="utf-8")
        yaml.safe_load(text)  # must be valid YAML
        referenced = set(ENTITY_RE.findall(text))
        assert referenced, file
        missing = sorted(e for e in referenced if hass.states.get(e) is None)
        assert not missing, f"{file.name}: {missing}"
