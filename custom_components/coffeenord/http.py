"""HTTP-Endpunkte für den Upload aus der App.

Authentifizierung übernimmt Home Assistant (requires_auth): Die App schickt einen
Long-Lived Access Token als Bearer-Token mit.
"""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, MAX_BATCH_SHOTS, MAX_SHOT_BYTES, STATUS_ERROR
from .models import parse_shot
from .shots import async_save_shot
from .store import ShotStore

_LOGGER = logging.getLogger(__name__)

# Ein Batch darf höchstens so groß sein wie alle seine Shots zusammen (plus Umschlag).
MAX_BATCH_BYTES = MAX_BATCH_SHOTS * MAX_SHOT_BYTES + 1024


def async_register_views(hass: HomeAssistant) -> None:
    """Views registrieren.

    Home Assistant kennt kein Abmelden, darum nur einmal pro Start.
    """
    flag = f"{DOMAIN}_views_registered"
    if hass.data.get(flag):
        return
    hass.http.register_view(ShotUploadView())
    hass.http.register_view(ShotBatchUploadView())
    hass.data[flag] = True


def _error(message: str, status: HTTPStatus) -> web.Response:
    return HomeAssistantView.json({"error": message}, status_code=status)


async def _read_json(
    request: web.Request, max_bytes: int
) -> tuple[Any, web.Response | None]:
    """Body lesen und als JSON parsen.

    Liefert (daten, None) oder (None, fehlerantwort).
    """
    if request.content_length is not None and request.content_length > max_bytes:
        _LOGGER.warning(
            "Upload abgelehnt: %s Bytes, erlaubt sind %s",
            request.content_length,
            max_bytes,
        )
        return None, _error("Payload zu groß", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    # content.read(n) liefert nur, was gerade gepuffert ist. Große Bodies kommen übers
    # Netz in mehreren Stücken an, darum bis zum Ende weiterlesen.
    body = bytearray()
    async for part in request.content.iter_chunked(64 * 1024):
        body.extend(part)
        if len(body) > max_bytes:
            _LOGGER.warning("Upload abgelehnt: mehr als %s Bytes", max_bytes)
            return None, _error("Payload zu groß", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    try:
        return json.loads(body), None
    except ValueError as err:
        _LOGGER.warning("Upload abgelehnt: ungültiges JSON (%s)", err)
        return None, _error("Ungültiges JSON", HTTPStatus.BAD_REQUEST)


def _store(hass: HomeAssistant) -> ShotStore | None:
    return hass.data.get(DOMAIN)


class ShotUploadView(HomeAssistantView):
    """Einen Shot hochladen (Upsert über shot_id)."""

    url = "/api/coffeenord/shots"
    name = "api:coffeenord:shots"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        store = _store(hass)
        if store is None:
            return _error(
                "CoffeeNørd ist nicht eingerichtet", HTTPStatus.SERVICE_UNAVAILABLE
            )

        data, error = await _read_json(request, MAX_SHOT_BYTES)
        if error is not None:
            return error
        try:
            shot = parse_shot(data)
        except vol.Invalid as err:
            _LOGGER.warning("Shot abgelehnt: %s", err)
            return _error(f"Ungültiger Shot: {err}", HTTPStatus.BAD_REQUEST)

        status = await async_save_shot(hass, store, shot)
        _LOGGER.debug("Shot %s: %s", shot.id, status)
        return self.json({"shot_id": shot.id, "status": status})


class ShotBatchUploadView(HomeAssistantView):
    """Mehrere Shots auf einmal hochladen, z. B. beim Erst-Import alter Brews.

    Fehlerhafte Shots werden einzeln gemeldet, die übrigen trotzdem gespeichert.
    """

    url = "/api/coffeenord/shots/batch"
    name = "api:coffeenord:shots:batch"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        store = _store(hass)
        if store is None:
            return _error(
                "CoffeeNørd ist nicht eingerichtet", HTTPStatus.SERVICE_UNAVAILABLE
            )

        data, error = await _read_json(request, MAX_BATCH_BYTES)
        if error is not None:
            return error
        shots = data.get("shots") if isinstance(data, dict) else None
        if not isinstance(shots, list):
            return _error('Erwartet wird {"shots": [...]}', HTTPStatus.BAD_REQUEST)
        if len(shots) > MAX_BATCH_SHOTS:
            return _error(
                f"Höchstens {MAX_BATCH_SHOTS} Shots pro Batch",
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        results = []
        for item in shots:
            shot_id = item.get("shot_id") if isinstance(item, dict) else None
            if len(json.dumps(item, separators=(",", ":"))) > MAX_SHOT_BYTES:
                _LOGGER.warning("Shot %s abgelehnt: größer als 2 MB", shot_id)
                results.append(
                    {
                        "shot_id": shot_id,
                        "status": STATUS_ERROR,
                        "error": "Shot zu groß",
                    }
                )
                continue
            try:
                shot = parse_shot(item)
            except vol.Invalid as err:
                _LOGGER.warning("Shot %s abgelehnt: %s", shot_id, err)
                results.append(
                    {"shot_id": shot_id, "status": STATUS_ERROR, "error": str(err)}
                )
                continue
            status = await async_save_shot(hass, store, shot)
            results.append({"shot_id": shot.id, "status": status})

        _LOGGER.debug(
            "Batch mit %s Shots: %s",
            len(shots),
            ", ".join(f"{r['shot_id']}={r['status']}" for r in results),
        )
        return self.json({"results": results})
