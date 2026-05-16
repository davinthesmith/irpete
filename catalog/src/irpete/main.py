"""Run Catalog: plain HTTP for local dev, or HTTPS when TLS paths are set."""

from __future__ import annotations

from typing import Any

import uvicorn

from irpete.app import create_app
from irpete.config import Settings, load_settings


def uvicorn_kwargs(settings: Settings) -> dict[str, Any]:
    """Arguments for ``uvicorn.run`` / ``uvicorn.Config`` (bind address, port, TLS)."""
    kw: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
    }
    if settings.tls_certfile is not None and settings.tls_keyfile is not None:
        kw["ssl_certfile"] = str(settings.tls_certfile)
        kw["ssl_keyfile"] = str(settings.tls_keyfile)
    return kw


def main() -> None:
    settings = load_settings()
    uvicorn.run(create_app(settings), log_level="info", **uvicorn_kwargs(settings))


if __name__ == "__main__":
    main()
