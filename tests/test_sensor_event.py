"""Tests für den Sensor „Letzter Shot“ und das Event coffeenord_shot_received."""

import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.coffeenord.const import DOMAIN, EVENT_SHOT_RECEIVED

from .payloads import make_shot

SHOTS_URL = "/api/coffeenord/shots"


def _entity_id(hass: HomeAssistant, entry) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_latest_shot"
    )
    assert entity_id is not None
    return entity_id


async def test_sensor_follows_latest_shot(
    hass: HomeAssistant, hass_client, hass_ws_client, setup_integration
) -> None:
    entity_id = _entity_id(hass, setup_integration)
    assert hass.states.get(entity_id).state == "unknown"

    client = await hass_client()
    await client.post(SHOTS_URL, json=make_shot())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "2025-11-12T09:52:31+00:00"
    assert state.attributes["bean_name"] == "Testbohne"
    assert state.attributes["ratio"] == 2.02
    assert "has_curves" not in state.attributes

    # Älterer Brühzeitpunkt verdrängt den neuesten Shot nicht
    await client.post(
        SHOTS_URL, json=make_shot(shot_id="alt", brewed_at=1000, updated_at=1000)
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["id"] == make_shot()["shot_id"]

    # Nach dem Löschen rückt der nächste nach
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": "coffeenord/shots/delete", "shot_id": make_shot()["shot_id"]}
    )
    assert (await ws.receive_json())["success"]
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["id"] == "alt"


async def test_event_only_for_fresh_new_shots(
    hass: HomeAssistant, hass_client, setup_integration
) -> None:
    events = async_capture_events(hass, EVENT_SHOT_RECEIVED)
    client = await hass_client()
    now = int(time.time())

    # Alter Brew (Erst-Import) → kein Event
    await client.post(SHOTS_URL, json=make_shot(shot_id="alt"))
    # Frischer neuer Shot → Event
    await client.post(
        SHOTS_URL, json=make_shot(shot_id="frisch", brewed_at=now, updated_at=now)
    )
    # Derselbe Shot bearbeitet → kein zweites Event
    await client.post(
        SHOTS_URL, json=make_shot(shot_id="frisch", brewed_at=now, updated_at=now + 5)
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    data = events[0].data
    assert data["shot_id"] == "frisch"
    assert data["bean_name"] == "Testbohne"
    assert data["dose_g"] == 18
    assert data["brew_time_s"] == 28.5
