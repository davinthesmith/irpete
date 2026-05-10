# Stage 1 — Peter: signal contract, SQLite, REST API, tests (no production TLS yet)

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are implementing **Peter’s core**: the **versioned JSON envelope**, **SQLite (WAL)** persistence, **FastAPI** routes with **Bearer authentication**, and **pytest** coverage. Production **TLS termination** is **Stage 3**; this stage may use **HTTP `TestClient`** for speed and CI simplicity, but the **HTTP surface and JSON shapes** must match what Stage 3 will later wrap in Uvicorn SSL without behavioral changes.

**Do not implement:** GPIO capture, systemd, Uvicorn TLS, Pete firmware.

---

## 2. Prerequisites

- Empty or early repo; no prior stage required.
- Python available locally for development (matching [REFERENCE.md §10](REFERENCE.md)).

---

## 3. Goals

1. **Freeze** the envelope schema and validation rules per [REFERENCE.md §6](REFERENCE.md).
2. Implement **SQLite** storage with **WAL** and a **`signals`** table per [REFERENCE.md §7](REFERENCE.md).
3. Expose **FastAPI** routes per [REFERENCE.md §5](REFERENCE.md) (except Pete-only `/v1/play`).
4. Enforce **`IRPETE_API_KEY`** Bearer auth on all protected routes (including `/v1/health` in v1).
5. Provide **`pytest`** proving: happy paths, 401/403 on bad/missing auth, validation failures on bad envelopes, uniqueness/upsert behavior as chosen.

---

## 4. Out of scope

- HTTPS / certificates / DNS.
- IR capture CLI.
- systemd.
- Any `firmware/pete/` code.

---

## 5. Technical design notes (research-backed)

### 5.1 FastAPI + Pydantic

Use **Pydantic v2** models for the envelope and for list/query responses. Keep **route handlers thin**; put validation in a dedicated module (e.g. `peter/irpete/validate.py`) so Stage 2 capture can reuse the same validation before DB insert.

**References:**

- FastAPI dependency injection for auth: [FastAPI Security — HTTPBearer](https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/)
- Pydantic validators for array length and numeric bounds.

### 5.2 SQLite WAL

On connection open (or pool checkout), run `PRAGMA journal_mode=WAL;` once. Use a single well-known path from `IRPETE_DB_PATH` with a sensible default under `peter/data/` for development.

### 5.3 `raw_us` first-pulse convention (must decide in code)

**IRremoteESP8266** `IRsend.sendRaw(uint16_t buf[], uint16_t len, uint8_t khz)` expects the first entry to be a **mark** duration (many examples assume mark-first). **TSOP modules** often yield a decoded stream where the **first edge after idle** may present as space-first in raw dumps.

**Stage 1 deliverable:** pick **one** of:

- **A)** Require mark-first in stored JSON and **reject** space-first captures in validation (Stage 2 must normalize), or  
- **B)** Allow either and **normalize** on `POST` to mark-first (preferred for operator ergonomics).

Document the choice in `README.md` and in module docstring; update [REFERENCE.md §6](REFERENCE.md) changelog if the written contract text must change.

### 5.4 `POST /v1/signals` semantics

Recommended v1: **upsert by `label`** from JSON body (idempotent reprogramming of the same button). Alternative: **409** on duplicate—only if you explicitly prefer strict create-only. **Pick one** and test it.

### 5.5 `GET /v1/signals` pagination

Even if v1 returns all rows, include **optional** `limit`/`offset` query params or document “may truncate in future.” Protect against multi-megabyte JSON by **not** embedding full `raw_us` in list view—return metadata + `label` + `updated_at` only.

---

## 6. Implementation checklist (suggested order)

1. Create `peter/pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pytest`, `httpx` (if needed).
2. Add package layout `peter/src/irpete/` (or `peter/irpete/` with src layout—pick one and document).
3. Implement `Envelope` Pydantic model + `validate_envelope(dict) -> Envelope`.
4. Implement SQLite repository: `upsert_signal`, `get_by_label`, `list_signals_meta`.
5. Implement FastAPI app + `HTTPBearer` security dependency comparing to `IRPETE_API_KEY`.
6. Wire routes; return consistent JSON error bodies (`{"detail": ...}` is fine).
7. Add `.env.example` with `IRPETE_API_KEY`, `IRPETE_DB_PATH`, optional `IRPETE_PORT`.
8. Add `README.md` section: “Stage 1 development run” using `uvicorn` **without** TLS on `127.0.0.1`.
9. Add `pytest` tests under `peter/tests/`.

---

## 7. Verification (exit criteria)

- [x] `pytest` passes locally with no hardware.
- [x] `POST` valid envelope → `GET` round-trips identical semantics (carrier + raw).
- [x] Invalid envelopes rejected with **422** (validation) or **400** (domain)—be consistent and tested.
- [x] Missing/wrong Bearer rejected with **401** or **403**—document which.
- [x] `GET /v1/signals/{label}` returns **404** for unknown label.
- [x] README explains how to run dev server and tests.

---

## 8. Handoff to Stage 2

Stage 2 will call **the same validation** and persistence logic from a **CLI** running on the Pi. Expose a **Python API** (functions) that Stage 2 can import, or a small internal module boundary, so capture does not duplicate validation rules.

**Artifacts Stage 2 depends on:**

- Stable `Envelope` / validation module.
- DB schema migration strategy (even if “manual SQL file” for v1).

---

## 9. To-do list (Stage 1 execution — start fresh)

- [x] Add `peter/` package skeleton + `pyproject.toml` (+ lockfile if using `uv`).
- [x] Implement Pydantic envelope model + validation (bounds, parity, carrier).
- [x] Implement SQLite schema + WAL pragma + repository functions.
- [x] Implement FastAPI routes: `/v1/health`, `/v1/signals`, `/v1/signals/{label}`, `POST /v1/signals`.
- [x] Implement Bearer auth dependency (`IRPETE_API_KEY`).
- [x] Add `.env.example` (no secrets).
- [x] Add `pytest` suite covering auth + validation + CRUD + list shape.
- [x] Add minimal `README.md` (dev run + test commands).
- [x] Run full verification §7 and tick boxes in PR/commit message.

---

## 10. References

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLite WAL](https://www.sqlite.org/wal.html)
- [Pydantic v2](https://docs.pydantic.dev/latest/)
