"""SQLite-Speicher für Shots.

Die Methoden sind synchron und werden über hass.async_add_executor_job aufgerufen,
damit der Event-Loop nicht blockiert. Weil dabei wechselnde Threads zugreifen,
schützt ein Lock die gemeinsame Verbindung.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .const import DB_VERSION, STATUS_CREATED, STATUS_UNCHANGED, STATUS_UPDATED
from .models import Shot

# Spalten, die aus einem Shot übernommen werden (ohne id, received_at, share_token).
SHOT_COLUMNS = (
    "schema_version",
    "brewed_at",
    "updated_at",
    "bean_name",
    "bean_roaster",
    "bean2_name",
    "mill_name",
    "preparation_name",
    "preparation_style",
    "grind_size",
    "dose_g",
    "yield_g",
    "brew_time_s",
    "ratio",
    "tds",
    "ey",
    "rating",
    "peak_pressure",
    "has_curves",
    "curves",
    "payload",
)

CREATE_STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """
    CREATE TABLE IF NOT EXISTS shots (
        id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL,
        brewed_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        received_at INTEGER NOT NULL,
        bean_name TEXT,
        bean_roaster TEXT,
        bean2_name TEXT,
        mill_name TEXT,
        preparation_name TEXT,
        preparation_style TEXT,
        grind_size TEXT,
        dose_g REAL,
        yield_g REAL,
        brew_time_s REAL,
        ratio REAL,
        tds REAL,
        ey REAL,
        rating REAL,
        peak_pressure REAL,
        has_curves INTEGER NOT NULL DEFAULT 0,
        curves TEXT NOT NULL DEFAULT '{}',
        payload TEXT NOT NULL,
        share_token TEXT UNIQUE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_shots_brewed_at ON shots (brewed_at)",
    "CREATE INDEX IF NOT EXISTS idx_shots_bean ON shots (bean_name)",
    "CREATE INDEX IF NOT EXISTS idx_shots_mill ON shots (mill_name)",
    "CREATE INDEX IF NOT EXISTS idx_shots_preparation ON shots (preparation_name)",
)


class ShotStore:
    """Zugriff auf die Shot-Datenbank."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        """Datenbank öffnen und bei Bedarf anlegen."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        with self._lock, conn:
            for statement in CREATE_STATEMENTS:
                conn.execute(statement)
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('db_version', ?)",
                (str(DB_VERSION),),
            )
        self._conn = conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @property
    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ShotStore ist nicht geöffnet")
        return self._conn

    def db_version(self) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM meta WHERE key = 'db_version'"
            ).fetchone()
        return int(row["value"])

    def upsert(self, shot: Shot) -> str:
        """Shot anlegen oder aktualisieren.

        Ist updated_at nicht neuer als der gespeicherte Stand, bleibt alles, wie es ist.
        share_token wird nie überschrieben.
        """
        values = _shot_values(shot)
        now = int(time.time())
        with self._lock, self._db as db:
            row = db.execute(
                "SELECT updated_at FROM shots WHERE id = ?", (shot.id,)
            ).fetchone()
            if row is None:
                columns = ("id", "received_at", *SHOT_COLUMNS)
                db.execute(
                    f"INSERT INTO shots ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' * len(columns))})",
                    (shot.id, now, *values),
                )
                return STATUS_CREATED
            if shot.updated_at <= row["updated_at"]:
                return STATUS_UNCHANGED
            assignments = ", ".join(f"{column} = ?" for column in SHOT_COLUMNS)
            db.execute(
                f"UPDATE shots SET {assignments}, received_at = ? WHERE id = ?",
                (*values, now, shot.id),
            )
            return STATUS_UPDATED

    def get(self, shot_id: str) -> dict[str, Any] | None:
        """Einen Shot mit Kurven (ohne Rohdatensatz) lesen."""
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM shots WHERE id = ?", (shot_id,)
            ).fetchone()
        if row is None:
            return None
        shot = dict(row)
        shot.pop("payload")
        shot["has_curves"] = bool(shot["has_curves"])
        shot["curves"] = json.loads(shot["curves"])
        return shot

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM shots").fetchone()[0]


def _shot_values(shot: Shot) -> tuple[Any, ...]:
    """Werte in der Reihenfolge von SHOT_COLUMNS."""
    values: dict[str, Any] = {
        column: getattr(shot, column)
        for column in SHOT_COLUMNS
        if column not in ("has_curves", "curves", "payload")
    }
    values["has_curves"] = int(shot.has_curves)
    values["curves"] = json.dumps(shot.curves, separators=(",", ":"))
    values["payload"] = json.dumps(shot.payload, separators=(",", ":"))
    return tuple(values[column] for column in SHOT_COLUMNS)
