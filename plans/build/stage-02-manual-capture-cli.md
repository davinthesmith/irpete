# Stage 2 — Peter: manual IR capture CLI (RAM → validate → commit)

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are adding a **Typer-based CLI** (or equivalent) that records **TSOP demodulated** pulse timings on a Raspberry Pi, holds the result **only in RAM** until validated, then **commits** to SQLite using the **same validation and persistence rules** as Stage 1’s `POST /v1/signals`.

**Assumption:** Stage 1 is **complete** (envelope validation + DB + tests exist).

**Do not implement:** TLS, systemd, Pete firmware, HTTP capture APIs (deferred in `plans/later.md`).

---

## 2. Prerequisites

- [ ] Stage 1 verification complete: `pytest` green; API models stable.
- [ ] Hardware: TSOP IR receiver wired with data to **BCM GPIO 18** ([REFERENCE.md §8](REFERENCE.md)).

---

## 3. Goals

1. **Manual start** and **manual stop** of recording (no idle-timeout auto-stop in v1).
2. While recording, accumulate transitions into an **in-memory** candidate envelope.
3. **`validate`** command (or flag) runs the **same** Pydantic/schema checks as HTTP `POST`.
4. **`commit --label …`** persists to SQLite with the given label (and merges/replaces per Stage 1 upsert policy).
5. Optional **`preview`** output: pulse count, total duration, first/last few `raw_us` values for human sanity check **before** commit.

---

## 4. Out of scope

- Auto-detecting “end of remote transmission” without operator stop.
- Storing partial captures after process crash (RAM-only until commit is intentional).
- Pete / Peter TLS.

---

## 5. Technical design notes (research-backed)

### 5.1 GPIO timing on Raspberry Pi OS

**Preferred:** `lgpio` on Pi 4/5 with Bookworm for **edge timing** with reasonable precision for IR (microsecond-scale). Record **relative deltas** between edges and build `raw_us` alternating mark/space per your Stage 1 convention.

**Fallbacks (document in README, do not block Stage 2 on Pi 5):**

- `pigpio` (historically common; Pi 5 support is nuanced—verify before recommending as primary).
- `RPi.GPIO` + threading + busy-wait is usually **not** sufficient for high-quality IR; avoid unless explicitly documented as low quality.

**Reference:** Raspberry Pi GPIO docs for **BCM numbering** vs physical pins.

### 5.2 CLI UX (recommended commands)

Pick one style and document:

**Style A — explicit verbs**

- `irpete-capture start` — begins session; errors if already active.
- `irpete-capture stop` — ends session; stores candidate in RAM buffer attached to process.
- `irpete-capture validate` — validates RAM candidate; prints errors or “OK”.
- `irpete-capture preview` — prints human summary (requires validated or raw? define).
- `irpete-capture commit --label foo` — writes DB.

**Style B — interactive**

- Single command opens REPL: `start`, user presses Enter to `stop`, then prompts `commit?`.

**Requirement:** **No SQLite write** occurs before **`commit`**.

### 5.3 Carrier frequency

TSOP path does not give carrier directly; **default `carrier_hz`** to `38000` in capture unless operator overrides via flag (`--carrier-hz`). Store explicit value in envelope.

### 5.4 Permissions

GPIO access often requires **`gpio`** group membership or **root**; document for the operator. Prefer least privilege (`sudo` only if unavoidable).

---

## 6. Implementation checklist (suggested order)

1. Add Typer entrypoint in `pyproject.toml` scripts, e.g. `irpete-capture`.
2. Implement `RecordingSession` state machine: `idle → recording → stopped_candidate`.
3. Implement GPIO edge loop: on `start`, arm; on `stop`, finalize `raw_us` array.
4. Reuse Stage 1 `validate_envelope` / Pydantic model for `validate` command.
5. Reuse Stage 1 repository `upsert_signal` for `commit`.
6. Add README “Training workflow” mirroring [REFERENCE workflow](REFERENCE.md) (manual steps).
7. Add minimal tests: **unit tests** with mocked GPIO timing array (no hardware in CI); optional marked `@pytest.mark.hardware` test skipped by default.

---

## 7. Verification (exit criteria)

- [ ] On Pi: `start` → press one remote button → `stop` → `validate` succeeds.
- [ ] `commit --label test_btn` then `GET https://...` (Stage 3) or Stage 1 dev `GET` shows stored envelope (Stage 2 early: use local HTTP GET from Stage 1 if TLS not ready).
- [ ] Invalid capture (e.g. empty) fails `validate` with actionable error.
- [ ] README lists **GPIO default 18**, wiring notes, and group/permission requirements.

**Minimum bar:** At least **one real remote** captured and visible via Peter `GET /v1/signals/{label}` before closing Stage 2 (HTTP vs HTTPS depends on whether Stage 3 is merged; if Stage 3 not merged yet, use Stage 1 HTTP dev server for GET verification).

---

## 8. Handoff to Stage 3

Stage 3 wraps the **same** FastAPI app in **Uvicorn TLS**. Ensure:

- App factory pattern supports `uvicorn irpete.main:app` unchanged.
- No TLS logic inside route handlers.

---

## 9. To-do list (Stage 2 execution — start fresh)

- [ ] Add Typer CLI package entry (`irpete-capture` or namespaced `irpete capture`).
- [ ] Implement GPIO recording backend (`lgpio` first) with configurable pin (default 18).
- [ ] Implement in-memory session buffer + manual start/stop.
- [ ] Wire `validate` to shared Pydantic validation from Stage 1.
- [ ] Wire `commit` to shared DB upsert from Stage 1.
- [ ] Add `preview` (optional but recommended).
- [ ] Add README: wiring, permissions, example session transcript.
- [ ] Add unit tests with mocked timing data; mark any hardware tests skipped by default.
- [ ] Perform real-remote verification §7.

---

## 10. References

- [Typer](https://typer.tiangolo.com/)
- [lgpio Python module](https://abyz.me.uk/lg/py_lgpio.html) (GPIO alerts / callbacks for edge timing)
- [rpi-lgpio (RPi.GPIO-compatible shim)](https://rpi-lgpio.readthedocs.io/) — optional if you standardize on RPi.GPIO-like API
- [BCM GPIO pinout](https://pinout.xyz/)
