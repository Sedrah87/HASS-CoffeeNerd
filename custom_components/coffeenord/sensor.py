"""Sensor „Letzter Shot“: Zeitpunkt des neuesten Shots, Kennzahlen als Attribute."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CoffeeNordConfigEntry
from .const import DOMAIN, SIGNAL_SHOTS_CHANGED, TITLE
from .store import ShotStore

# Zusammenfassungsfelder, die nicht als Attribut erscheinen.
HIDDEN_ATTRIBUTES = ("brewed_at", "updated_at", "has_curves")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoffeeNordConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([LatestShotSensor(entry.entry_id, entry.runtime_data)])


class LatestShotSensor(SensorEntity):
    """Neuester Shot nach Brühzeitpunkt (nicht nach Upload-Zeitpunkt)."""

    _attr_has_entity_name = True
    _attr_translation_key = "latest_shot"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_should_poll = False

    def __init__(self, entry_id: str, store: ShotStore) -> None:
        self._store = store
        self._attr_unique_id = f"{entry_id}_latest_shot"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=TITLE,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._latest: dict[str, Any] | None = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_SHOTS_CHANGED, self._schedule)
        )
        await self._async_refresh()

    @callback
    def _schedule(self) -> None:
        self.hass.async_create_task(self._async_refresh(write=True))

    async def _async_refresh(self, write: bool = False) -> None:
        self._latest = await self.hass.async_add_executor_job(self._store.latest)
        if write:
            self.async_write_ha_state()

    @property
    def native_value(self) -> datetime | None:
        if self._latest is None:
            return None
        return dt_util.utc_from_timestamp(self._latest["brewed_at"])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._latest is None:
            return None
        return {
            key: value
            for key, value in self._latest.items()
            if key not in HIDDEN_ATTRIBUTES
        }
