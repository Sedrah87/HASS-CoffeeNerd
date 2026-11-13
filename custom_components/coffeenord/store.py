"""SQLite-Speicher für Shots.

Die Methoden sind synchron und werden über hass.async_add_executor_job aufgerufen,
damit der Event-Loop nicht blockiert. Weil dabei wechselnde Threads zugreifen,
schützt ein Lock die gemeinsame Verbindung.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .const import DB_VERSION, STATUS_CREATED, STATUS_UNCHANGED, STATUS_UPDATED
from .models import Shot, parse_shot

_LOGGER = logging.getLogger(__name__)

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

# Spalten der Zusammenfassung (Liste, Sensor, Event), ohne Kurven und Rohdaten.
SUMMARY_COLUMNS = (
    "id",
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
)
_SUMMARY_SELECT = f"SELECT {', '.join(SUMMARY_COLUMNS)} FROM shots"

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
            version = int(
                conn.execute(
                    "SELECT value FROM meta WHERE key = 'db_version'"
                ).fetchone()["value"]
            )
            if version < 2:
                _recalculate_curves(conn)
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'db_version'",
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

    def list(
        self,
        *,
        bean: str | None = None,
        mill: str | None = None,
        preparation: str | None = None,
        brewed_from: int | None = None,
        brewed_to: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Zusammenfassungen, neueste zuerst, und die Gesamtzahl der Treffer.

        Der Bohnen-Filter trifft auch die zweite Bohne eines Blend-Shots.
        """
        conditions: list[str] = []
        params: list[Any] = []
        if bean is not None:
            conditions.append("(bean_name = ? OR bean2_name = ?)")
            params += [bean, bean]
        if mill is not None:
            conditions.append("mill_name = ?")
            params.append(mill)
        if preparation is not None:
            conditions.append("preparation_name = ?")
            params.append(preparation)
        if brewed_from is not None:
            conditions.append("brewed_at >= ?")
            params.append(brewed_from)
        if brewed_to is not None:
            conditions.append("brewed_at <= ?")
            params.append(brewed_to)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._lock:
            total = self._db.execute(
                f"SELECT COUNT(*) FROM shots{where}", params
            ).fetchone()[0]
            rows = self._db.execute(
                f"{_SUMMARY_SELECT}{where} "
                "ORDER BY brewed_at DESC, id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [_summary(row) for row in rows], total

    def latest(self) -> dict[str, Any] | None:
        """Zusammenfassung des zuletzt gebrühten Shots."""
        with self._lock:
            row = self._db.execute(
                f"{_SUMMARY_SELECT} ORDER BY brewed_at DESC, id LIMIT 1"
            ).fetchone()
        return _summary(row) if row is not None else None

    def filter_values(self) -> dict[str, list[str]]:
        """Vorhandene Bohnen, Mühlen und Zubereitungen für die Auswahllisten."""
        with self._lock:
            beans = self._db.execute(
                "SELECT bean_name FROM shots WHERE bean_name IS NOT NULL "
                "UNION SELECT bean2_name FROM shots WHERE bean2_name IS NOT NULL "
                "ORDER BY 1"
            ).fetchall()
            mills = self._db.execute(
                "SELECT DISTINCT mill_name FROM shots WHERE mill_name IS NOT NULL "
                "ORDER BY 1"
            ).fetchall()
            preparations = self._db.execute(
                "SELECT DISTINCT preparation_name FROM shots "
                "WHERE preparation_name IS NOT NULL ORDER BY 1"
            ).fetchall()
        return {
            "beans": [row[0] for row in beans],
            "mills": [row[0] for row in mills],
            "preparations": [row[0] for row in preparations],
        }

    def delete(self, shot_id: str) -> bool:
        """Shot löschen. Liefert False, wenn es ihn nicht gab."""
        with self._lock, self._db as db:
            return db.execute("DELETE FROM shots WHERE id = ?", (shot_id,)).rowcount > 0

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM shots").fetchone()[0]


def _summary(row: sqlite3.Row) -> dict[str, Any]:
    summary = dict(row)
    summary["has_curves"] = bool(summary["has_curves"])
    return summary


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


def _recalculate_curves(conn: sqlite3.Connection) -> None:
    """Migration auf db_version 2: Kurven aus dem Rohdatensatz neu berechnen.

    Version 1 las die Zeit aus brew_time und ließ Werte vor dem Tarieren stehen, die
    Kurven sprangen dadurch zurück. Der Rohdatensatz ist unverändert gespeichert, darum
    lassen sich alle Shots ohne neuen Upload korrigieren.
    """
    rows = conn.execute("SELECT id, payload FROM shots").fetchall()
    for row in rows:
        try:
            shot = parse_shot(json.loads(row["payload"]))
        except Exception:  # noqa: BLE001 - ein kaputter Datensatz darf den Start nicht verhindern
            _LOGGER.warning("Kurven von Shot %s nicht neu berechnet", row["id"])
            continue
        conn.execute(
            "UPDATE shots SET curves = ?, has_curves = ?, peak_pressure = ? "
            "WHERE id = ?",
            (
                json.dumps(shot.curves, separators=(",", ":")),
                int(shot.has_curves),
                shot.peak_pressure,
                row["id"],
            ),
        )
    if rows:
        _LOGGER.info("Kurven von %s Shots neu berechnet", len(rows))
