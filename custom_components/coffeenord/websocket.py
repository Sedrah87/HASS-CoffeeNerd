"""WebSocket-Commands für das Panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .shots import async_delete_shot
from .store import ShotStore

ERR_NOT_LOADED = "not_loaded"


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Commands registrieren. Wie die Views nur einmal pro Start."""
    flag = f"{DOMAIN}_websocket_registered"
    if hass.data.get(flag):
        return
    websocket_api.async_register_command(hass, ws_list_shots)
    websocket_api.async_register_command(hass, ws_get_shot)
    websocket_api.async_register_command(hass, ws_filter_values)
    websocket_api.async_register_command(hass, ws_delete_shot)
    hass.data[flag] = True


def _store(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg_id: int
) -> ShotStore | None:
    store: ShotStore | None = hass.data.get(DOMAIN)
    if store is None:
        connection.send_error(
            msg_id, ERR_NOT_LOADED, "CoffeeNørd ist nicht eingerichtet"
        )
    return store


@websocket_api.websocket_command(
    {
        vol.Required("type"): "coffeenord/shots/list",
        vol.Optional("bean"): str,
        vol.Optional("mill"): str,
        vol.Optional("preparation"): str,
        vol.Optional("shape"): str,
        vol.Optional("from"): vol.Coerce(int),
        vol.Optional("to"): vol.Coerce(int),
        vol.Optional("limit", default=50): vol.All(int, vol.Range(min=1, max=200)),
        vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
    }
)
@websocket_api.async_response
async def ws_list_shots(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Shot-Liste (nur Zusammenfassungen), neueste zuerst."""
    if (store := _store(hass, connection, msg["id"])) is None:
        return
    shots, total = await hass.async_add_executor_job(
        lambda: store.list(
            bean=msg.get("bean"),
            mill=msg.get("mill"),
            preparation=msg.get("preparation"),
            shape=msg.get("shape"),
            brewed_from=msg.get("from"),
            brewed_to=msg.get("to"),
            limit=msg["limit"],
            offset=msg["offset"],
        )
    )
    connection.send_result(msg["id"], {"shots": shots, "total": total})


@websocket_api.websocket_command(
    {vol.Required("type"): "coffeenord/shots/get", vol.Required("shot_id"): str}
)
@websocket_api.async_response
async def ws_get_shot(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Ein Shot mit Kurven."""
    if (store := _store(hass, connection, msg["id"])) is None:
        return
    shot = await hass.async_add_executor_job(store.get, msg["shot_id"])
    if shot is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Shot nicht gefunden"
        )
        return
    connection.send_result(msg["id"], shot)


@websocket_api.websocket_command({vol.Required("type"): "coffeenord/filters"})
@websocket_api.async_response
async def ws_filter_values(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Vorhandene Bohnen, Mühlen, Zubereitungen und Profile."""
    if (store := _store(hass, connection, msg["id"])) is None:
        return
    connection.send_result(
        msg["id"], await hass.async_add_executor_job(store.filter_values)
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "coffeenord/shots/delete", vol.Required("shot_id"): str}
)
@websocket_api.async_response
async def ws_delete_shot(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Shot löschen (nur Admins)."""
    if (store := _store(hass, connection, msg["id"])) is None:
        return
    if not await async_delete_shot(hass, store, msg["shot_id"]):
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Shot nicht gefunden"
        )
        return
    connection.send_result(msg["id"])
