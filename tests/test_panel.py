"""Tests für das Seitenleisten-Panel."""

from http import HTTPStatus

from homeassistant.core import HomeAssistant

from custom_components.coffeenord.panel import PANEL_URL_PATH


async def test_panel_registered_and_removed(
    hass: HomeAssistant, hass_client, setup_integration
) -> None:
    panels = hass.data["frontend_panels"]
    assert PANEL_URL_PATH in panels
    panel = panels[PANEL_URL_PATH]
    assert panel.require_admin
    module_url = panel.config["_panel_custom"]["module_url"]
    assert module_url.startswith("/coffeenord_static/coffeenord-panel.js?v=")

    client = await hass_client()
    response = await client.get(module_url)
    assert response.status == HTTPStatus.OK
    assert "coffeenord-panel" in await response.text()

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    assert PANEL_URL_PATH not in hass.data["frontend_panels"]
