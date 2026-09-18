from __future__ import annotations

import hashlib
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
    weak_aliases_json TEXT NOT NULL DEFAULT '[]',
    native_names_json TEXT NOT NULL DEFAULT '[]',
    dob TEXT,
    dobs_json TEXT NOT NULL DEFAULT '[]',
    countries_json TEXT NOT NULL DEFAULT '[]',
    programs_json TEXT NOT NULL DEFAULT '[]',
    identifiers_json TEXT NOT NULL DEFAULT '{}',
    source_url TEXT,
    remarks TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_source ON watchlist_entities(source);
CREATE INDEX IF NOT EXISTS idx_watchlist_name ON watchlist_entities(primary_name);

CREATE TABLE IF NOT EXISTS source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    sha256 TEXT,
    record_count INTEGER NOT NULL,
    added_count INTEGER,
    removed_count INTEGER,
    source_url TEXT,
    parser_version TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_snapshot_source ON source_snapshots(source, created_at);

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


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(watchlist_entities)").fetchall()}
    additions = {
        "weak_aliases_json": "TEXT NOT NULL DEFAULT '[]'",
        "native_names_json": "TEXT NOT NULL DEFAULT '[]'",
        "dobs_json": "TEXT NOT NULL DEFAULT '[]'",
        "identifiers_json": "TEXT NOT NULL DEFAULT '{}'",
    }
    for name, ddl in additions.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE watchlist_entities ADD COLUMN {name} {ddl}")


def init_db(path: Path | str | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        _ensure_columns(conn)
        conn.commit()


def _values(r: dict) -> tuple:
    dobs = list(dict.fromkeys([str(x) for x in (r.get("dobs") or []) if x]))
    if r.get("dob") and str(r["dob"]) not in dobs:
        dobs.insert(0, str(r["dob"]))
    return (
        str(r.get("source", "custom")),
        str(r.get("source_id") or r.get("id") or r.get("primary_name")),
        str(r.get("entity_type", "unknown")),
        str(r.get("primary_name", "")).strip(),
        json.dumps(r.get("aliases", []) or [], ensure_ascii=False),
        json.dumps(r.get("weak_aliases", []) or [], ensure_ascii=False),
        json.dumps(r.get("native_names", []) or [], ensure_ascii=False),
        (dobs[0] if dobs else r.get("dob")) or None,
        json.dumps(dobs, ensure_ascii=False),
        json.dumps(r.get("countries", []) or [], ensure_ascii=False),
        json.dumps(r.get("programs", []) or [], ensure_ascii=False),
        json.dumps(r.get("identifiers", {}) or {}, ensure_ascii=False),
        r.get("source_url") or None,
        r.get("remarks") or None,
        json.dumps(r.get("raw", r), ensure_ascii=False, default=str),
    )


UPSERT_SQL = """
INSERT INTO watchlist_entities (
  source, source_id, entity_type, primary_name, aliases_json, weak_aliases_json,
  native_names_json, dob, dobs_json, countries_json, programs_json, identifiers_json,
  source_url, remarks, raw_json, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(source, source_id) DO UPDATE SET
  entity_type=excluded.entity_type,
  primary_name=excluded.primary_name,
  aliases_json=excluded.aliases_json,
  weak_aliases_json=excluded.weak_aliases_json,
  native_names_json=excluded.native_names_json,
  dob=excluded.dob,
  dobs_json=excluded.dobs_json,
  countries_json=excluded.countries_json,
  programs_json=excluded.programs_json,
  identifiers_json=excluded.identifiers_json,
  source_url=excluded.source_url,
  remarks=excluded.remarks,
  raw_json=excluded.raw_json,
  updated_at=CURRENT_TIMESTAMP
"""


def _upsert_conn(conn: sqlite3.Connection, rows: list[dict]) -> int:
    values = [_values(r) for r in rows if str(r.get("primary_name", "")).strip()]
    if values:
        conn.executemany(UPSERT_SQL, values)
    return len(values)


def upsert_entities(rows: Iterable[dict], path: Path | str | None = None) -> int:
    materialized = list(rows)
    if not materialized:
        return 0
    with connect(path) as conn:
        count = _upsert_conn(conn, materialized)
        conn.commit()
    return count


def replace_source_atomic(
    source: str,
    rows: Iterable[dict],
    path: Path | str | None = None,
    *,
    snapshot: dict | None = None,
    allow_empty: bool = False,
) -> dict:
    materialized = [dict(r) for r in rows if str(r.get("primary_name", "")).strip()]
    for r in materialized:
        r["source"] = source
    if not materialized and not allow_empty:
        raise ValueError("Refusing to replace a source with an empty dataset")

    with connect(path) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            previous_ids = {
                str(row[0]) for row in conn.execute(
                    "SELECT source_id FROM watchlist_entities WHERE source=?", (source,)
                ).fetchall()
            }
            previous = len(previous_ids)
            new_ids = {str(r.get("source_id") or r.get("id") or r.get("primary_name")) for r in materialized}
            added_count = len(new_ids - previous_ids)
            removed_count = len(previous_ids - new_ids)
            conn.execute("DELETE FROM watchlist_entities WHERE source=?", (source,))
            inserted = _upsert_conn(conn, materialized)
            snap = snapshot or {}
            conn.execute(
                """INSERT INTO source_snapshots
                (source, sha256, record_count, added_count, removed_count, source_url, parser_version, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source,
                    snap.get("sha256"),
                    inserted,
                    added_count,
                    removed_count,
                    snap.get("source_url"),
                    snap.get("parser_version"),
                    json.dumps(snap.get("metadata", {}), ensure_ascii=False),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {
        "source": source,
        "previous": previous,
        "inserted": inserted,
        "added": added_count,
        "removed": removed_count,
    }


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            d["weak_aliases"] = json.loads(d.pop("weak_aliases_json") or "[]")
            d["native_names"] = json.loads(d.pop("native_names_json") or "[]")
            d["dobs"] = json.loads(d.pop("dobs_json") or "[]")
            d["countries"] = json.loads(d.pop("countries_json") or "[]")
            d["programs"] = json.loads(d.pop("programs_json") or "[]")
            d["identifiers"] = json.loads(d.pop("identifiers_json") or "{}")
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


def latest_snapshot(source: str, path: Path | str | None = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM source_snapshots WHERE source=? ORDER BY id DESC LIMIT 1", (source,)
        ).fetchone()
        return dict(row) if row else None


def stats(path: Path | str | None = None) -> dict:
    with connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM watchlist_entities").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM screening_events").fetchone()[0]
        snapshots = conn.execute("SELECT COUNT(*) FROM source_snapshots").fetchone()[0]
        by_source = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT source, COUNT(*) FROM watchlist_entities GROUP BY source ORDER BY source"
            ).fetchall()
        }
    return {"entities": total, "screenings": events, "source_snapshots": snapshots, "by_source": by_source}
