# IRPete — common reference (shared across all build stages)

**Purpose:** This file is the **stable contract** between sequential implementation sessions. A new agent or developer should read this **before** opening a stage plan. Stage plans **point here** instead of repeating fragile details in multiple places.

**If this file disagrees with a stage plan:** update **this file** first (with a short changelog note at the bottom), then align the stage plan.

---

## 1. Project vocabulary

| Term | Meaning |
|------|---------|
| **Peter** | Raspberry Pi **IR host**: HTTPS REST API + SQLite storage for labeled IR signal envelopes; optional capture CLI. |
| **Pete** | **Wemos D1 Mini** (ESP8266) **IR repeater**: HTTPS client to Peter; HTTPS server for `/v1/play`; drives IR LED via firmware. |
| **Envelope** | Versioned **JSON IR signal** payload (the wire format and DB payload). |
| **Label** | Unique human-chosen string key for one stored envelope (e.g. `tv_power`). |
| **TSOP capture** | IR received through a **demodulating** IR receiver module (TSOP38xx class). v1 assumes **post-detector** timing arrays, not pre-demodulator “photodiode raw.” |

---

## 2. Repository layout (canonical paths)

All implementers should converge on these paths unless a stage plan explicitly migrates them.

| Path | Owner | Description |
|------|--------|-------------|
| `peter/` | Peter | Python package: FastAPI app, SQLite access, Typer CLIs, tests; systemd unit under `peter/deploy/systemd/`. |
| `firmware/pete/` | Pete | PlatformIO project for ESP8266 D1 Mini. |
| `plans/build/` | Meta | This reference + per-stage execution plans. |
| `plans/later.md` | Meta | Explicitly **deferred** work (OTA, WiFiManager, etc.). |

**Root `README.md`:** should exist by Stage 3–4 with operator-facing install notes; stage plans may create it incrementally.

---

## 3. DNS and TLS naming (LAN)

| Hostname | Role |
|----------|------|
| `peter.toomanyprojects.dev` | Peter’s **HTTPS** API (Raspberry Pi). |
| `pete.toomanyprojects.dev` | **Optional** DNS name for documentation or stable client config; the D1 Mini still obtains a LAN IP via DHCP unless you pin it. |

**Certificates:** You can issue **`*.toomanyprojects.dev`** (wildcard) or per-service certs. Peter uses **server fullchain + private key** on disk. Pete embeds a **trust anchor** (typically the **issuing CA** PEM, or a minimal chain) so **leaf rotation** does not require reflashing a fingerprint every time—as long as the same CA signs the new leaf.

**TLS verification rules:**

- **Hostname / SNI** must match the certificate SAN/CN in use (`peter.toomanyprojects.dev` for Peter).
- **No plain-HTTP “success” paths** on the LAN for v1 (development may use HTTP **only** where Stage 1 explicitly allows `TestClient` on localhost without TLS).

---

## 4. Authentication (v1)

**Standard:** `Authorization: Bearer <token>` on **every** protected route (including `/v1/health` if exposed—v1 uses **one shared API key** for simplicity).

**Environment variable (Peter):**

- `IRPETE_API_KEY` — long random secret; never commit.

**Firmware (Pete):**

- Store API key in **gitignored** `secrets.h` (or equivalent) alongside Wi‑Fi credentials and trust PEM.

**Key rotation (operational):** regenerate key → update Peter env → update Pete secrets → restart Peter → reflash or OTA-update Pete (OTA is deferred; see `plans/later.md`).

---

## 5. REST API surface (v1)

Base path prefix: **`/v1`**.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/health` | Liveness; same Bearer auth as other routes in v1. |
| `GET` | `/v1/signals` | List labels + metadata (avoid shipping full `raw_us` for every row if large). |
| `GET` | `/v1/signals/{label}` | Return **full envelope** for that label (404 if missing). |
| `POST` | `/v1/signals` | Create or replace signal by **body** `label` (or by URL—pick one in Stage 1 and document; **do not change without bumping `schema_version` policy**). |

**Pete (Stage 6+):**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/play` | Body JSON includes **`label`** (and optional fields later); Pete fetches envelope from Peter then transmits IR. **409 Conflict** if a play is already in progress. |

**Play sequencing invariant:** **fetch envelope from Peter (TLS) completes**, then **IR transmission** begins. **No overlapping** TLS client sessions and IR timing on ESP8266.

---

## 6. Signal envelope (JSON contract)

This is the **canonical on-wire and in-DB** representation (minor field naming may be adjusted in Stage 1, but semantics must stay).

### Required fields

| Field | Type | Notes |
|-------|------|------|
| `schema_version` | integer | Start at `1`; increment only on breaking JSON changes. |
| `label` | string | Unique key; stable charset (recommend: `^[a-z0-9_\\-]{1,64}$`). |
| `carrier_hz` | integer | Typical `38000` for consumer IR; store explicit value. |
| `raw_us` | array of integers | Alternating **on/off** durations in **microseconds** for v1 TSOP-learned captures. **First element convention (Stage 1):** stored envelopes are **mark-first** (first entry is an on pulse). On `POST /v1/signals`, if the first duration exceeds **50 ms**, Peter treats it as a **leading idle gap** and **removes it once** so the array matches `sendRaw`’s mark-first expectation. |

### Optional fields (v1 reserved, may be unused)

| Field | Type | Notes |
|-------|------|------|
| `repeat` | integer | Repeat count semantics TBD; prefer default behavior in firmware until needed. |
| `notes` | string | Human operator notes (not required for replay). |

### Normalization rules (must be documented in code + README)

Implementers must pick **one** canonical rule set in Stage 1 and validate on `POST`:

- **Max length** of `raw_us` (guard ESP8266 RAM and JSON size). **v1:** max **512** elements.
- **Min/max per element** (reject absurd pulses). **v1:** **1–65535** µs (uint16-friendly).
- **Odd length** handling: `raw_us` length parity policy (IRremoteESP8266 expects a specific mark/space lead—normalize or reject). **v1:** odd lengths are allowed after normalization (no parity restriction beyond min length).
- **Carrier bounds** (e.g. 30_000–60_000 Hz) unless extended later.

### v1 capture semantics

Training hardware is **TSOP-class** (demodulated). The envelope is **“learned remote” style** data comparable to many consumer bridges—not guaranteed equivalent to a professional IR analyzer’s pre-demodulator capture.

---

## 7. SQLite persistence (Peter)

**Recommended pragmas:** `journal_mode=WAL`, `foreign_keys=ON`, sensible `synchronous` default.

**Table `signals` (conceptual):**

- `id` — integer PK autoincrement.
- `label` — unique text **not null**.
- `envelope_json` — text **not null** (store full envelope JSON, or normalized subset—**store enough** for `GET` to return full contract).
- `created_at` — UTC timestamp default now.
- `updated_at` — optional.

**Uniqueness:** `label` must be unique; `POST` semantics are **upsert** or **reject duplicates**—choose one in Stage 1 and document.

---

## 8. Hardware defaults

### Peter (Raspberry Pi)

| Signal | Default GPIO | Notes |
|--------|--------------|------|
| TSOP data pin | **BCM GPIO 18** | Physically **pin 12** on the 40-pin header; matches user breadboard photos. |
| TSOP VCC / GND | 3V3 or 5V per module datasheet | Must match module; wiring is operator responsibility. |

**Capture backend:** prefer **`lgpio`** on modern Raspberry Pi OS; document fallback for older Pis in Stage 2 README notes.

### Pete (D1 Mini / ESP8266)

| Function | Default pin | ESP8266 GPIO |
|----------|-------------|--------------|
| IR send (LED + driver) | **`D2`** | GPIO4 |

**IR circuit:** GPIO must not be abused for high current; use **transistor + resistor** for the IR LED for reliable range (document in Stage 7).

---

## 9. Environment variables (Peter)

| Variable | Stage | Required | Purpose |
|----------|-------|----------|---------|
| `IRPETE_API_KEY` | 1+ | yes | Bearer token validation. |
| `IRPETE_DB_PATH` | 1+ | recommended | SQLite file path (default sensible for dev under `peter/data/`). |
| `IRPETE_TLS_CERTFILE` | 3+ | yes (prod) | Server certificate **fullchain** PEM. |
| `IRPETE_TLS_KEYFILE` | 3+ | yes (prod) | Server private key PEM. |
| `IRPETE_HOST` | 3+ | optional | Bind address (default `0.0.0.0`). |
| `IRPETE_PORT` | 1+ | optional | Listen port. **Dev (HTTP):** default **8000**. **Prod (HTTPS):** recommended **8443** (avoids binding port 443 without capabilities). |

Use **`.env.example`** in repo; never commit real `.env`.

---

## 10. Tooling versions (guidance, not law)

Pin versions in project files when created:

- **Python:** 3.11+ recommended on Pi OS Bookworm.
- **FastAPI / Uvicorn / Pydantic:** current stable at time of implementation.
- **PlatformIO:** current stable; `board = d1_mini`, `platform = espressif8266`.

---

## 11. Testing expectations

| Layer | Tooling | When |
|-------|---------|------|
| Peter unit/API | `pytest`, `httpx` or Starlette `TestClient` | Stage 1+; Stage 8 in CI. |
| Peter TLS | `curl` against LAN hostname | Stage 3+. |
| Pete compile | `pio run` | Stage 5+; Stage 8 in CI. |
| Pete HIL | Manual checklist (IR LED + receiver or camera) | Stage 5–7 README. |

**CI does not replace HIL:** ESP8266 timing and real remotes need bench verification.

---

## 12. Security and secrets handling

- **Never** commit: API keys, private keys, fullchain PEMs, `secrets.h`, operator `.env`.
- **Do** commit: `.env.example`, `secrets.h.example`, systemd **templates** with **no secrets inlined**.
- Prefer **0600** permissions for key material on the Pi.

---

## 13. Stage gate checklist (quick)

Use between sessions:

- [ ] Previous stage **Verification** completed and noted in git/PR description.
- [ ] **REFERENCE.md** still matches reality (or was updated with changelog).
- [ ] Next stage plan read in full before coding.

---

## 14. Per-stage execution plans

Verbose, session-oriented plans live beside this file:

| Stage | Document |
|------:|----------|
| 1 | [stage-01-peter-contract-and-core.md](stage-01-peter-contract-and-core.md) |
| 2 | [stage-02-manual-capture-cli.md](stage-02-manual-capture-cli.md) |
| 3 | [stage-03-peter-https-dns.md](stage-03-peter-https-dns.md) |
| 4 | [stage-04-peter-systemd.md](stage-04-peter-systemd.md) |
| 5 | [stage-05-pete-tls-client-ir.md](stage-05-pete-tls-client-ir.md) |
| 6 | [stage-06-pete-https-play-api.md](stage-06-pete-https-play-api.md) |
| 7 | [stage-07-hardware-abstraction-docs.md](stage-07-hardware-abstraction-docs.md) |
| 8 | [stage-08-ci-release-hygiene.md](stage-08-ci-release-hygiene.md) |

Index with usage instructions: [README.md](README.md).

---

## 15. Changelog (reference)

| Date | Change |
|------|--------|
| 2026-05-10 | Stage 4 Peter: §2 `peter/deploy/systemd/irpete-peter.service` + `peter/deploy/peter.env.example`; production env on Pi as `/etc/irpete/peter.env` (0600). |
| 2026-05-10 | Stage 3 Peter: §9 `IRPETE_PORT` defaults clarified (8000 dev HTTP, 8443 recommended for LAN HTTPS); TLS env vars `IRPETE_TLS_CERTFILE` / `IRPETE_TLS_KEYFILE`; optional `IRPETE_DISABLE_OPENAPI`. |
| 2026-05-10 | Initial `plans/build`: REFERENCE (incl. §14 stage index), README, verbose stage plans 1–8. |
