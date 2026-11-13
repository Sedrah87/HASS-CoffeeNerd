"""CoffeeNørd: Shots aus der CoffeeNørd-App in Home Assistant speichern und anzeigen."""

from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DB_DIR, DB_FILE, DOMAIN
from .http import async_register_views
from .store import ShotStore

type CoffeeNordConfigEntry = ConfigEntry[ShotStore]


async def async_setup_entry(hass: HomeAssistant, entry: CoffeeNordConfigEntry) -> bool:
    """Datenbank öffnen und Upload-Endpunkte bereitstellen."""
    store = ShotStore(Path(hass.config.path(DB_DIR, DB_FILE)))
    await hass.async_add_executor_job(store.open)
    entry.runtime_data = store
    # Die Views bleiben bis zum Neustart registriert und holen sich den Store von hier.
    # Ohne Eintrag antworten sie mit 503.
    hass.data[DOMAIN] = store
    async_register_views(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoffeeNordConfigEntry) -> bool:
    """Datenbank schließen."""
    hass.data.pop(DOMAIN, None)
    await hass.async_add_executor_job(entry.runtime_data.close)
    return True
