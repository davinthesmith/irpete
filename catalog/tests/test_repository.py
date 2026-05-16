"""SQLite repository and pragma tests (no live server)."""

from __future__ import annotations

import json
from pathlib import Path

from irpete.repository import connect, get_by_label, init_db, upsert_signal
from irpete.validate import Envelope, validate_envelope


def _env(label: str = "x") -> Envelope:
    return validate_envelope(
        {
            "schema_version": 1,
            "label": label,
            "carrier_hz": 38000,
            "raw_us": [1000, 500, 1000, 500],
        }
    )


def test_connect_uses_wal_mode(tmp_path: Path) -> None:
    p = tmp_path / "t.db"
    conn = connect(p)
    try:
        init_db(conn)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert int(fk) == 1
    finally:
        conn.close()


def test_upsert_round_trip_json(tmp_path: Path) -> None:
    p = tmp_path / "t.db"
    conn = connect(p)
    try:
        init_db(conn)
        e = _env("round")
        upsert_signal(conn, e)
        conn.commit()
    finally:
        conn.close()

    conn = connect(p)
    try:
        row = get_by_label(conn, "round")
        assert row is not None
        assert row["label"] == "round"
        assert row["carrier_hz"] == 38000
        assert row["raw_us"] == [1000, 500, 1000, 500]
        # Stored JSON is valid for API response shape
        json.dumps(row)
    finally:
        conn.close()
