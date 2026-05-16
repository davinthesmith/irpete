"""Environment-backed settings for the Catalog service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_default_db_path() -> Path:
    """Default SQLite path under `catalog/data/` relative to this package root."""
    # catalog/src/irpete/config.py -> catalog/
    catalog_root = Path(__file__).resolve().parents[2]
    return catalog_root / "data" / "irpete.db"


def _env_truthy(name: str) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    api_key: str
    db_path: Path
    host: str
    port: int
    tls_certfile: Path | None = None
    tls_keyfile: Path | None = None
    disable_openapi: bool = False


def resolve_db_path() -> Path:
    """SQLite path from ``IRPETE_DB_PATH`` or the default under ``catalog/data/``."""
    db = os.environ.get("IRPETE_DB_PATH", "").strip()
    return Path(db) if db else _repo_default_db_path()


def load_settings() -> Settings:
    key = os.environ.get("IRPETE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("IRPETE_API_KEY is required")

    db_path = resolve_db_path()

    host = os.environ.get("IRPETE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_s = os.environ.get("IRPETE_PORT", "8000").strip()
    try:
        port = int(port_s)
    except ValueError as e:
        raise RuntimeError(f"IRPETE_PORT must be an integer, got {port_s!r}") from e

    cert_s = os.environ.get("IRPETE_TLS_CERTFILE", "").strip()
    key_s = os.environ.get("IRPETE_TLS_KEYFILE", "").strip()
    tls_certfile: Path | None = None
    tls_keyfile: Path | None = None
    if cert_s or key_s:
        if not cert_s or not key_s:
            raise RuntimeError(
                "IRPETE_TLS_CERTFILE and IRPETE_TLS_KEYFILE must both be set "
                "when enabling TLS (or omit both for plain HTTP development)."
            )
        tls_certfile = Path(cert_s)
        tls_keyfile = Path(key_s)
        if not tls_certfile.is_file():
            raise RuntimeError(f"IRPETE_TLS_CERTFILE is not a readable file: {tls_certfile}")
        if not tls_keyfile.is_file():
            raise RuntimeError(f"IRPETE_TLS_KEYFILE is not a readable file: {tls_keyfile}")

    disable_openapi = _env_truthy("IRPETE_DISABLE_OPENAPI")

    return Settings(
        api_key=key,
        db_path=db_path,
        host=host,
        port=port,
        tls_certfile=tls_certfile,
        tls_keyfile=tls_keyfile,
        disable_openapi=disable_openapi,
    )
