"""Shot speichern und die Folgen auslösen (Sensor aktualisieren, Event feuern)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    EVENT_MAX_AGE_SECONDS,
    EVENT_SHOT_RECEIVED,
    SIGNAL_SHOTS_CHANGED,
    STATUS_CREATED,
    STATUS_UNCHANGED,
)
from .models import Shot
from .store import ShotStore

# Kennzahlen im Event, damit Automationen ohne weiteren Aufruf auskommen.
EVENT_FIELDS = (
    "brewed_at",
    "bean_name",
    "bean2_name",
    "mill_name",
    "preparation_name",
    "preparation_style",
    "grind_size",
    "dose_g",
    "yield_g",
    "brew_time_s",
    "ratio",
    "peak_pressure",
    "shape",
    "main_flow",
    "grind_hint",
)


async def async_save_shot(hass: HomeAssistant, store: ShotStore, shot: Shot) -> str:
    """Shot speichern. Liefert created, updated oder unchanged."""
    status = await hass.async_add_executor_job(store.upsert, shot)
    if status == STATUS_UNCHANGED:
        return status

    async_dispatcher_send(hass, SIGNAL_SHOTS_CHANGED)
    # Event nur für neue, frische Shots: Nachträglich bearbeitete oder beim
    # Erst-Import hochgeladene alte Brews sollen keine Automationen starten.
    age = dt_util.utcnow().timestamp() - shot.brewed_at
    if status == STATUS_CREATED and age <= EVENT_MAX_AGE_SECONDS:
        data = {"shot_id": shot.id}
        data.update({field: getattr(shot, field) for field in EVENT_FIELDS})
        hass.bus.async_fire(EVENT_SHOT_RECEIVED, data)
    return status


async def async_delete_shot(
    hass: HomeAssistant, store: ShotStore, shot_id: str
) -> bool:
    deleted = await hass.async_add_executor_job(store.delete, shot_id)
    if deleted:
        async_dispatcher_send(hass, SIGNAL_SHOTS_CHANGED)
    return deleted
