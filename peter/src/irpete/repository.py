"""SQLite persistence for signal envelopes (WAL mode)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from irpete.validate import Envelope


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL UNIQUE,
  envelope_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def upsert_signal(conn: sqlite3.Connection, envelope: Envelope) -> None:
    blob = envelope.model_dump(mode="json")
    conn.execute(
        """
        INSERT INTO signals (label, envelope_json, created_at, updated_at)
        VALUES (?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(label) DO UPDATE SET
          envelope_json = excluded.envelope_json,
          updated_at = datetime('now')
        """,
        (envelope.label, json.dumps(blob)),
    )


def get_by_label(conn: sqlite3.Connection, label: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT envelope_json FROM signals WHERE label = ?", (label,)
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["envelope_json"])


@dataclass(frozen=True)
class SignalMeta:
    label: str
    schema_version: int
    carrier_hz: int
    updated_at: str


def list_signals_meta(
    conn: sqlite3.Connection, *, limit: int = 100, offset: int = 0
) -> list[SignalMeta]:
    cur = conn.execute(
        """
        SELECT label, envelope_json, updated_at
        FROM signals
        ORDER BY label COLLATE NOCASE ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    out: list[SignalMeta] = []
    for row in cur.fetchall():
        env = json.loads(row["envelope_json"])
        out.append(
            SignalMeta(
                label=row["label"],
                schema_version=int(env.get("schema_version", 1)),
                carrier_hz=int(env["carrier_hz"]),
                updated_at=str(row["updated_at"]),
            )
        )
    return out


def count_signals(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM signals").fetchone()
    return int(row["c"]) if row else 0
