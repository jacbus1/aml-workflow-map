from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

DB_PATH = Path(os.environ.get("SCREENING_DB", "data/screening.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS watchlist_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'unknown',
    primary_name TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    dob TEXT,
    countries_json TEXT NOT NULL DEFAULT '[]',
    programs_json TEXT NOT NULL DEFAULT '[]',
    source_url TEXT,
    remarks TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_source ON watchlist_entities(source);
CREATE INDEX IF NOT EXISTS idx_watchlist_name ON watchlist_entities(primary_name);
CREATE TABLE IF NOT EXISTS screening_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    query_name TEXT NOT NULL,
    query_dob TEXT,
    query_country TEXT,
    threshold REAL NOT NULL,
    candidate_count INTEGER NOT NULL,
    matched_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _path(path: Path | str | None = None) -> Path:
    p = Path(path) if path else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect(path: Path | str | None = None):
    conn = sqlite3.connect(_path(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db(path: Path | str | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def upsert_entities(rows: Iterable[dict], path: Path | str | None = None) -> int:
    sql = """
    INSERT INTO watchlist_entities (
      source, source_id, entity_type, primary_name, aliases_json, dob,
      countries_json, programs_json, source_url, remarks, raw_json, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(source, source_id) DO UPDATE SET
      entity_type=excluded.entity_type,
      primary_name=excluded.primary_name,
      aliases_json=excluded.aliases_json,
      dob=excluded.dob,
      countries_json=excluded.countries_json,
      programs_json=excluded.programs_json,
      source_url=excluded.source_url,
      remarks=excluded.remarks,
      raw_json=excluded.raw_json,
      updated_at=CURRENT_TIMESTAMP
    """
    values = []
    for r in rows:
        values.append((
            str(r.get("source", "custom")),
            str(r.get("source_id") or r.get("id") or r.get("primary_name")),
            str(r.get("entity_type", "unknown")),
            str(r.get("primary_name", "")).strip(),
            json.dumps(r.get("aliases", []), ensure_ascii=False),
            r.get("dob") or None,
            json.dumps(r.get("countries", []), ensure_ascii=False),
            json.dumps(r.get("programs", []), ensure_ascii=False),
            r.get("source_url") or None,
            r.get("remarks") or None,
            json.dumps(r.get("raw", r), ensure_ascii=False, default=str),
        ))
    if not values:
        return 0
    with connect(path) as conn:
        conn.executemany(sql, values)
        conn.commit()
    return len(values)


def get_entities(path: Path | str | None = None, source: str | None = None) -> list[dict]:
    with connect(path) as conn:
        if source:
            cur = conn.execute("SELECT * FROM watchlist_entities WHERE source=?", (source,))
        else:
            cur = conn.execute("SELECT * FROM watchlist_entities")
        out = []
        for row in cur.fetchall():
            d = dict(row)
            d["aliases"] = json.loads(d.pop("aliases_json") or "[]")
            d["countries"] = json.loads(d.pop("countries_json") or "[]")
            d["programs"] = json.loads(d.pop("programs_json") or "[]")
            out.append(d)
        return out


def clear_source(source: str, path: Path | str | None = None) -> int:
    with connect(path) as conn:
        cur = conn.execute("DELETE FROM watchlist_entities WHERE source=?", (source,))
        conn.commit()
        return cur.rowcount


def record_screening(event: dict, path: Path | str | None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO screening_events
            (request_id, query_name, query_dob, query_country, threshold, candidate_count, matched_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event["request_id"], event["query_name"], event.get("query_dob"),
                event.get("query_country"), event["threshold"], event["candidate_count"],
                event["matched_count"],
            ),
        )
        conn.commit()


def stats(path: Path | str | None = None) -> dict:
    with connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM watchlist_entities").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM screening_events").fetchone()[0]
        by_source = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT source, COUNT(*) FROM watchlist_entities GROUP BY source ORDER BY source"
            ).fetchall()
        }
    return {"entities": total, "screenings": events, "by_source": by_source}
