# IRPete — Peter (Stage 1)

Peter exposes a versioned JSON **envelope** API backed by **SQLite (WAL)**. Authentication is a single shared **`IRPETE_API_KEY`** passed as `Authorization: Bearer <token>` on **every** `/v1` route, including **`GET /v1/health`**.

Shared contract: [`plans/build/REFERENCE.md`](../plans/build/REFERENCE.md).

**Auth errors:** missing or wrong `Authorization: Bearer` returns **401 Unauthorized** (with `WWW-Authenticate: Bearer`).

## Stage 1 — development run (HTTP, no TLS)

From this directory (`peter/`):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # edit IRPETE_API_KEY
export $(grep -v '^#' .env | xargs)   # or use direnv / manual export
python -m irpete.main
```

Equivalent with uvicorn factory (loads settings from the environment):

```bash
export IRPETE_API_KEY=dev-secret
uvicorn irpete.app:create_app --factory --host 127.0.0.1 --port 8000
```

The API listens on **`IRPETE_HOST` / `IRPETE_PORT`** (defaults **`127.0.0.1:8000`**). SQLite defaults to **`data/irpete.db`** under `peter/` when **`IRPETE_DB_PATH`** is unset.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Envelope semantics (Stage 1)

- **`POST /v1/signals`** **upserts by `label`** (same label replaces the stored envelope).
- **`raw_us` mark-first normalization:** IRremoteESP8266 `sendRaw` expects the first entry to be a **mark**. On POST, if the first duration is **greater than 50 ms**, it is treated as a leading idle gap and **removed once** so the stored array starts with a mark-oriented timing sequence. Values must fit **uint16** on the wire (1–65535 µs per element). Length is capped at **512** elements for v1.

## Schema migration (v1)

DDL lives in [`schema.sql`](schema.sql) and is applied automatically on startup via `irpete.repository.init_db`. For manual provisioning, run that SQL against your SQLite file once.
