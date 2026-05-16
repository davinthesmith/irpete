"""Environment-backed settings for the Peter service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_default_db_path() -> Path:
    """Default SQLite path under `peter/data/` relative to this package root."""
    # peter/src/irpete/config.py -> peter/
    peter_root = Path(__file__).resolve().parents[2]
    return peter_root / "data" / "irpete.db"


@dataclass(frozen=True)
class Settings:
    api_key: str
    db_path: Path
    host: str
    port: int


def load_settings() -> Settings:
    key = os.environ.get("IRPETE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("IRPETE_API_KEY is required")

    db = os.environ.get("IRPETE_DB_PATH", "").strip()
    db_path = Path(db) if db else _repo_default_db_path()

    host = os.environ.get("IRPETE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_s = os.environ.get("IRPETE_PORT", "8000").strip()
    try:
        port = int(port_s)
    except ValueError as e:
        raise RuntimeError(f"IRPETE_PORT must be an integer, got {port_s!r}") from e

    return Settings(api_key=key, db_path=db_path, host=host, port=port)
