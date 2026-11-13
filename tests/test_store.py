"""Tests für den SQLite-Speicher."""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from custom_components.coffeenord.const import (
    DB_VERSION,
    STATUS_CREATED,
    STATUS_UNCHANGED,
    STATUS_UPDATED,
)
from custom_components.coffeenord.models import parse_shot
from custom_components.coffeenord.store import ShotStore

from .payloads import make_shot


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ShotStore]:
    shot_store = ShotStore(tmp_path / "coffeenord" / "shots.db")
    shot_store.open()
    yield shot_store
    shot_store.close()


def test_creates_database_with_version(store: ShotStore, tmp_path: Path) -> None:
    assert (tmp_path / "coffeenord" / "shots.db").exists()
    assert store.db_version() == DB_VERSION
    assert store.count() == 0


def test_upsert_created_unchanged_updated(store: ShotStore) -> None:
    assert store.upsert(parse_shot(make_shot())) == STATUS_CREATED
    # Gleicher Stand noch einmal → keine Änderung, kein Duplikat
    assert store.upsert(parse_shot(make_shot())) == STATUS_UNCHANGED
    # Älterer Stand überschreibt nicht
    assert store.upsert(parse_shot(make_shot(updated_at=1))) == STATUS_UNCHANGED

    changed = make_shot(updated_at=1762949999)
    changed["visualizer"]["bean"]["name"] = "Andere Bohne"
    assert store.upsert(parse_shot(changed)) == STATUS_UPDATED

    assert store.count() == 1
    assert store.get(changed["shot_id"])["bean_name"] == "Andere Bohne"


def test_get_returns_curves_without_payload(store: ShotStore) -> None:
    payload = make_shot()
    store.upsert(parse_shot(payload))

    shot = store.get(payload["shot_id"])

    assert "payload" not in shot
    assert shot["has_curves"] is True
    assert shot["curves"]["pressure"] == [[5.0, 8.7], [15.0, 9.1]]
    assert shot["share_token"] is None


def test_get_unknown_shot(store: ShotStore) -> None:
    assert store.get("gibt-es-nicht") is None


def test_update_keeps_share_token(store: ShotStore) -> None:
    payload = make_shot()
    store.upsert(parse_shot(payload))
    store._db.execute(
        "UPDATE shots SET share_token = 'geheim' WHERE id = ?", (payload["shot_id"],)
    )

    store.upsert(parse_shot(make_shot(updated_at=1762949999)))

    assert store.get(payload["shot_id"])["share_token"] == "geheim"


def test_reopen_keeps_data(tmp_path: Path) -> None:
    path = tmp_path / "shots.db"
    first = ShotStore(path)
    first.open()
    first.upsert(parse_shot(make_shot()))
    first.close()

    second = ShotStore(path)
    second.open()
    assert second.count() == 1
    second.close()


def _add(store: ShotStore, shot_id: str, brewed_at: int, **visualizer) -> None:
    payload = make_shot(shot_id=shot_id, brewed_at=brewed_at, updated_at=brewed_at)
    for section, values in visualizer.items():
        payload["visualizer"][section].update(values)
    store.upsert(parse_shot(payload))


def test_list_newest_first_with_total(store: ShotStore) -> None:
    for index in range(5):
        _add(store, f"id-{index}", 1000 + index)

    shots, total = store.list(limit=2, offset=1)

    assert total == 5
    assert [shot["id"] for shot in shots] == ["id-3", "id-2"]
    assert "curves" not in shots[0]
    assert shots[0]["has_curves"] is True


def test_list_filters(store: ShotStore) -> None:
    _add(store, "a", 1000, bean={"name": "Kenia"}, mill={"name": "Niche"})
    _add(store, "b", 2000, bean={"name": "Brasil"}, mill={"name": "Niche"})
    blend = make_shot(
        shot_id="c", brewed_at=3000, updated_at=3000, bean2={"name": "Kenia"}
    )
    blend["visualizer"]["preparation"]["name"] = "V60"
    store.upsert(parse_shot(blend))

    assert {s["id"] for s in store.list(bean="Kenia")[0]} == {"a", "c"}
    assert {s["id"] for s in store.list(mill="Niche")[0]} == {"a", "b"}
    assert {s["id"] for s in store.list(preparation="V60")[0]} == {"c"}
    assert {s["id"] for s in store.list(brewed_from=1500, brewed_to=2500)[0]} == {"b"}
    assert store.list(bean="Kenia", mill="Niche")[1] == 1


def test_latest_and_filter_values(store: ShotStore) -> None:
    assert store.latest() is None
    _add(store, "neu", 2000, bean={"name": "Brasil"})
    _add(store, "alt", 1000, bean={"name": "Kenia"})

    assert store.latest()["id"] == "neu"
    assert store.filter_values() == {
        "beans": ["Brasil", "Kenia"],
        "mills": ["Testmühle"],
        "preparations": ["Siebträger"],
    }


def test_delete(store: ShotStore) -> None:
    _add(store, "weg", 1000)

    assert store.delete("weg") is True
    assert store.delete("weg") is False
    assert store.count() == 0


def test_migration_recalculates_curves(tmp_path: Path) -> None:
    """Shots aus db_version 1 bekommen beim Öffnen neu berechnete Kurven."""
    path = tmp_path / "coffeenord" / "shots.db"
    shot_store = ShotStore(path)
    shot_store.open()
    shot_store.upsert(parse_shot(make_shot()))
    shot_store.close()
    # Zustand von Version 1 nachstellen: alte Kurven und alte Versionsnummer.
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE shots SET curves = ?", (json.dumps({"weight": [[0.1, 9]]}),)
        )
        conn.execute("UPDATE meta SET value = '1' WHERE key = 'db_version'")

    shot_store = ShotStore(path)
    shot_store.open()
    shot = shot_store.get(make_shot()["shot_id"])
    shot_store.close()

    assert shot_store_version(path) == DB_VERSION
    assert shot["curves"] == parse_shot(make_shot()).curves


def shot_store_version(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return int(
            conn.execute("SELECT value FROM meta WHERE key = 'db_version'").fetchone()[
                0
            ]
        )
