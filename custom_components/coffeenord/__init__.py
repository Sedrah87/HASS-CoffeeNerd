"""CoffeeNørd: Shots aus der CoffeeNørd-App in Home Assistant speichern und anzeigen."""

from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DB_DIR, DB_FILE, DOMAIN
from .http import async_register_views
from .panel import async_register_panel, async_unregister_panel
from .store import ShotStore
from .websocket import async_register_commands

PLATFORMS = [Platform.SENSOR]

type CoffeeNordConfigEntry = ConfigEntry[ShotStore]


async def async_setup_entry(hass: HomeAssistant, entry: CoffeeNordConfigEntry) -> bool:
    """Datenbank öffnen, Endpunkte, Commands, Panel und Sensor bereitstellen."""
    store = ShotStore(Path(hass.config.path(DB_DIR, DB_FILE)))
    await hass.async_add_executor_job(store.open)
    entry.runtime_data = store
    # Views und Commands bleiben bis zum Neustart registriert und holen sich den
    # Store von hier. Ohne Eintrag antworten sie mit einem Fehler.
    hass.data[DOMAIN] = store
    async_register_views(hass)
    async_register_commands(hass)
    await async_register_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoffeeNordConfigEntry) -> bool:
    """Sensor und Panel entfernen, Datenbank schließen."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    async_unregister_panel(hass)
    hass.data.pop(DOMAIN, None)
    await hass.async_add_executor_job(entry.runtime_data.close)
    return True
