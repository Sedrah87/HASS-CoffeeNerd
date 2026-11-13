"""Tests für die Upload-Endpunkte."""

import json
from http import HTTPStatus
from pathlib import Path

from homeassistant.core import HomeAssistant

from custom_components.coffeenord.const import MAX_BATCH_SHOTS, MAX_SHOT_BYTES

from .payloads import make_shot

SHOTS_URL = "/api/coffeenord/shots"
BATCH_URL = "/api/coffeenord/shots/batch"


async def test_upload_requires_auth(hass_client_no_auth, setup_integration) -> None:
    client = await hass_client_no_auth()

    response = await client.post(SHOTS_URL, json=make_shot())

    assert response.status == HTTPStatus.UNAUTHORIZED


async def test_upload_created_then_unchanged(
    hass: HomeAssistant, hass_client, setup_integration, tmp_path: Path
) -> None:
    client = await hass_client()

    response = await client.post(SHOTS_URL, json=make_shot())
    assert response.status == HTTPStatus.OK
    assert await response.json() == {
        "shot_id": make_shot()["shot_id"],
        "status": "created",
    }

    response = await client.post(SHOTS_URL, json=make_shot())
    assert (await response.json())["status"] == "unchanged"

    assert (tmp_path / "coffeenord" / "shots.db").exists()
    assert setup_integration.runtime_data.count() == 1


async def test_upload_invalid_json(hass_client, setup_integration) -> None:
    client = await hass_client()

    response = await client.post(
        SHOTS_URL, data="{kaputt", headers={"Content-Type": "application/json"}
    )

    assert response.status == HTTPStatus.BAD_REQUEST


async def test_upload_invalid_shot(hass_client, setup_integration) -> None:
    client = await hass_client()

    response = await client.post(SHOTS_URL, json=make_shot(shot_id=""))

    assert response.status == HTTPStatus.BAD_REQUEST
    assert "Ungültiger Shot" in (await response.json())["error"]


async def test_upload_too_large(hass_client, setup_integration) -> None:
    client = await hass_client()

    response = await client.post(
        SHOTS_URL, json=make_shot(polster="x" * (MAX_SHOT_BYTES + 1))
    )

    assert response.status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE


async def test_batch_mixed_results(hass_client, setup_integration) -> None:
    client = await hass_client()
    second = make_shot(shot_id="3f1c2a4e-0000-4000-8000-000000000002")

    response = await client.post(
        BATCH_URL,
        json={"shots": [make_shot(), make_shot(shot_id=""), second, "kein Objekt"]},
    )

    assert response.status == HTTPStatus.OK
    results = (await response.json())["results"]
    assert [result["status"] for result in results] == [
        "created",
        "error",
        "created",
        "error",
    ]
    assert results[1]["shot_id"] == ""
    assert results[3]["shot_id"] is None
    assert setup_integration.runtime_data.count() == 2


async def test_batch_limit(hass_client, setup_integration) -> None:
    client = await hass_client()
    shots = [make_shot(shot_id=f"id-{index}") for index in range(MAX_BATCH_SHOTS + 1)]

    response = await client.post(BATCH_URL, json={"shots": shots})

    assert response.status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert setup_integration.runtime_data.count() == 0


async def test_batch_requires_list(hass_client, setup_integration) -> None:
    client = await hass_client()

    response = await client.post(BATCH_URL, json={"shots": "nein"})

    assert response.status == HTTPStatus.BAD_REQUEST


async def test_unavailable_after_unload(
    hass: HomeAssistant, hass_client, setup_integration
) -> None:
    client = await hass_client()
    assert await hass.config_entries.async_unload(setup_integration.entry_id)

    response = await client.post(SHOTS_URL, json=make_shot())

    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE


async def test_batch_body_in_chunks(hass_client, setup_integration) -> None:
    """Große Bodies kommen übers Netz in mehreren Stücken an, nicht am Stück."""
    client = await hass_client()
    shots = [make_shot(shot_id=f"chunk-{i}", padding="x" * 50_000) for i in range(10)]
    body = json.dumps({"shots": shots}).encode()

    async def stuecke():
        for start in range(0, len(body), 16_384):
            yield body[start : start + 16_384]

    response = await client.post(
        BATCH_URL, data=stuecke(), headers={"Content-Type": "application/json"}
    )

    assert response.status == HTTPStatus.OK
    results = (await response.json())["results"]
    assert [r["status"] for r in results] == ["created"] * 10
