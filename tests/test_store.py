"""Tests für den SQLite-Speicher."""

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
