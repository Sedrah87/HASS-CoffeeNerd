"""Tests für die WebSocket-Commands."""

from homeassistant.core import HomeAssistant

from custom_components.coffeenord.models import parse_shot

from .payloads import make_shot


async def _send(ws, message: dict) -> dict:
    await ws.send_json_auto_id(message)
    return await ws.receive_json()


async def test_list_get_filters(
    hass: HomeAssistant, hass_ws_client, setup_integration
) -> None:
    store = setup_integration.runtime_data
    store.upsert(parse_shot(make_shot(shot_id="a", brewed_at=1000, updated_at=1000)))
    store.upsert(parse_shot(make_shot(shot_id="b", brewed_at=2000, updated_at=2000)))
    ws = await hass_ws_client(hass)

    result = await _send(ws, {"type": "coffeenord/shots/list", "limit": 1})
    assert result["success"]
    assert result["result"]["total"] == 2
    assert [shot["id"] for shot in result["result"]["shots"]] == ["b"]

    result = await _send(ws, {"type": "coffeenord/shots/list", "from": 1500})
    assert [shot["id"] for shot in result["result"]["shots"]] == ["b"]

    result = await _send(ws, {"type": "coffeenord/shots/get", "shot_id": "a"})
    assert result["success"]
    assert result["result"]["curves"]["weight"][-1] == [28.5, 36.4]

    result = await _send(ws, {"type": "coffeenord/filters"})
    assert result["result"]["beans"] == ["Testbohne"]


async def test_get_unknown_and_invalid_limit(
    hass: HomeAssistant, hass_ws_client, setup_integration
) -> None:
    ws = await hass_ws_client(hass)

    result = await _send(ws, {"type": "coffeenord/shots/get", "shot_id": "nix"})
    assert not result["success"]
    assert result["error"]["code"] == "not_found"

    result = await _send(ws, {"type": "coffeenord/shots/list", "limit": 1000})
    assert not result["success"]
    assert result["error"]["code"] == "invalid_format"


async def test_delete_requires_admin(
    hass: HomeAssistant, hass_ws_client, hass_admin_user, setup_integration
) -> None:
    setup_integration.runtime_data.upsert(parse_shot(make_shot(shot_id="a")))
    hass_admin_user.groups = []
    ws = await hass_ws_client(hass)

    result = await _send(ws, {"type": "coffeenord/shots/delete", "shot_id": "a"})

    assert not result["success"]
    assert result["error"]["code"] == "unauthorized"
    assert setup_integration.runtime_data.count() == 1


async def test_not_loaded(
    hass: HomeAssistant, hass_ws_client, setup_integration
) -> None:
    ws = await hass_ws_client(hass)
    assert await hass.config_entries.async_unload(setup_integration.entry_id)

    result = await _send(ws, {"type": "coffeenord/shots/list"})

    assert not result["success"]
    assert result["error"]["code"] == "not_loaded"
