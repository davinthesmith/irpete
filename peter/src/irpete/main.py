"""Run Peter over HTTP (no TLS — Stage 1 / local development)."""

from __future__ import annotations

import uvicorn

from irpete.app import create_app
from irpete.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
