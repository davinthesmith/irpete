"""FastAPI application: `/v1` REST API for IR signal envelopes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from irpete.config import Settings, load_settings
from irpete.repository import (
    connect,
    count_signals,
    get_by_label,
    init_db,
    list_signals_meta,
    upsert_signal,
)
from irpete.validate import validate_envelope

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request):
    settings = request.app.state.settings
    conn = connect(settings.db_path)
    init_db(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def require_api_key(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    token = creds.credentials.strip() if creds and creds.credentials else ""
    if not creds or token != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


DbDep = Annotated[Any, Depends(get_db)]


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = load_settings()

    docs_kw: dict[str, Any] = {}
    if settings.disable_openapi:
        docs_kw = {"docs_url": None, "redoc_url": None, "openapi_url": None}

    app = FastAPI(title="IRPete Peter", version="0.1.0", **docs_kw)
    app.state.settings = settings

    @app.get("/v1/health", dependencies=[Depends(require_api_key)])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/signals", dependencies=[Depends(require_api_key)])
    def list_signals(
        db: DbDep,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        """List labels and metadata only (no ``raw_us``)."""
        rows = list_signals_meta(db, limit=limit, offset=offset)
        total = count_signals(db)
        return {
            "items": [
                {
                    "label": r.label,
                    "schema_version": r.schema_version,
                    "carrier_hz": r.carrier_hz,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ],
            "limit": limit,
            "offset": offset,
            "total": total,
        }

    @app.get("/v1/signals/{label}", dependencies=[Depends(require_api_key)])
    def get_signal(db: DbDep, label: str) -> dict[str, Any]:
        env = get_by_label(db, label)
        if env is None:
            raise HTTPException(status_code=404, detail=f"Unknown label: {label}")
        return env

    @app.post("/v1/signals", dependencies=[Depends(require_api_key)])
    def post_signal(db: DbDep, body: dict[str, Any]) -> dict[str, Any]:
        from pydantic import ValidationError

        try:
            env = validate_envelope(body, normalize=True)
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=e.errors(include_context=False, include_url=False),
            ) from e
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        upsert_signal(db, env)
        return env.model_dump(mode="json")

    return app
