"""Gemeinsame Fixtures."""

from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.coffeenord.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """custom_components/ in jedem Test laden."""
    return


@pytest.fixture
async def setup_integration(hass: HomeAssistant, tmp_path: Path) -> MockConfigEntry:
    """Integration einrichten, Datenbank im temporären Verzeichnis."""
    hass.config.config_dir = str(tmp_path)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
