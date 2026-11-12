"""CoffeeNørd: Shots aus der CoffeeNørd-App in Home Assistant speichern und anzeigen."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration für einen Config-Eintrag einrichten."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config-Eintrag entladen."""
    return True
