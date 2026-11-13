"""Seitenleisten-Panel „Shots“ (gebautes Bundle aus dem Ordner frontend/)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL_PATH = DOMAIN
PANEL_ELEMENT = "coffeenord-panel"
PANEL_TITLE = "Shots"
PANEL_ICON = "mdi:coffee"
STATIC_URL = f"/{DOMAIN}_static"
FRONTEND_DIR = Path(__file__).parent / "frontend"
BUNDLE = "coffeenord-panel.js"


def _bundle_hash() -> str:
    """Kurzer Hash des Bundles.

    Als ?v= an der URL lädt der Browser nach einem Update nicht den alten Stand.
    """
    return hashlib.sha256((FRONTEND_DIR / BUNDLE).read_bytes()).hexdigest()[:12]


async def async_register_panel(hass: HomeAssistant) -> None:
    flag = f"{DOMAIN}_static_registered"
    if not hass.data.get(flag):
        # Statische Pfade lassen sich nicht abmelden, darum nur einmal pro Start.
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        hass.data[flag] = True

    version = await hass.async_add_executor_job(_bundle_hash)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_ELEMENT,
        frontend_url_path=PANEL_URL_PATH,
        module_url=f"{STATIC_URL}/{BUNDLE}?v={version}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=True,
        config={},
    )


def async_unregister_panel(hass: HomeAssistant) -> None:
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
