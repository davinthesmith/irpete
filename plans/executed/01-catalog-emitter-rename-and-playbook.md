# Executed plan — Catalog / Emitter rename, operator playbook, CI alignment

**Common reference:** [../build/REFERENCE.md](../build/REFERENCE.md)

**Source:** This plan is derived from the **git staged** snapshot at authoring time (branch `init/stage-09` in the workspace where it was written). It documents what that change set implements so future work can treat it as a completed migration narrative, not a forward-looking build stage.

---

## 1. Execution context

The repository previously used **Peter** (Raspberry Pi Python service) and **Pete** (ESP8266 firmware) as internal names and directory roots. Staged work **renames those roles** to **Catalog** and **Emitter**, updates **paths and identifiers** across Python, firmware, CI, and docs, and **consolidates** standalone manual validation prose into a single operator-facing playbook.

**Intent:** Align names with product language, keep the HTTP API contract under `/v1/*` stable where unchanged by diff, and give operators one linear document from bench bring-up through hardware sign-off.

---

## 2. Goals (what the staged change set achieves)

1. **Directory migration:** `peter/` → `catalog/` (Python package layout, deploy templates, scripts, tests, egg-info paths).
2. **Firmware migration:** `firmware/pete/` → `firmware/emitter/` with source renames (`peter_tls_client` → `catalog_tls_client`, `pete_https_play` → `emitter_https_play`, and related symbols/comments).
3. **Secrets template:** `firmware/emitter/include/secrets.h.example` documents **Catalog** host/CA and **Emitter** HTTPS server PEMs (replacing Pete/Peter-oriented names in the prior tree).
4. **Operator docs:** Remove root `MANUAL_VALIDATION.md`; add `PLAYBOOK.md` (BOM, wiring, Catalog install, Emitter build/secrets, first closed-loop `curl`, embedded manual validation checklist).
5. **Root README:** Refresh top-level narrative to point at `catalog/`, `firmware/emitter/`, and `PLAYBOOK.md`.
6. **CI:** `.github/workflows/ci.yml` uses `working-directory: catalog` and `firmware/emitter`, pip cache path `catalog/pyproject.toml`, PlatformIO cache key hashing `firmware/emitter/platformio.ini`.
7. **Backlog hygiene:** `plans/later.md` headings and bullets use Catalog / Emitter wording (e.g. mDNS example `emitter.local`, Home Assistant calling Emitter’s `/v1/play`).
8. **Small code/doc cleanups in Catalog:** Default DB path under `catalog/data/`, docstrings and user-facing strings say “Catalog” / “Emitter”; stage-number references in comments trimmed where touched.

---

## 3. Deliverables checklist (maps to staged files)

- [ ] **Rename tree:** Git records `peter/*` → `catalog/*` and `firmware/pete/*` → `firmware/emitter/*` (including test rename `test_firmware_pete_contract.py` → `test_firmware_emitter_contract.py`).
- [ ] **Systemd / deploy:** `irpete-catalog.service`, `catalog.env.example`, `run-catalog-https.sh` naming and contents aligned with Catalog paths.
- [ ] **PLAYBOOK.md** present; **MANUAL_VALIDATION.md** absent (content superseded by playbook section 6 and cross-links).
- [ ] **CI** green on a push: pytest from `catalog/`, `pio run` from `firmware/emitter`.
- [ ] **Firmware** builds with updated include paths and `secrets.h` defines (`CATALOG_*`, `EMITTER_*`, etc., per staged `secrets.h.example` and `main.cpp`).

---

## 4. Technical notes (for maintainers)

- **Default SQLite path:** Resolved relative to package root now under `catalog/` (see `catalog/src/irpete/config.py` in the staged rename).
- **Contract tests:** README / systemd / firmware README / CI path contracts in `catalog/tests/test_*_contract.py` are updated to assert new paths and service names where the diff touches them.
- **Firmware behavior:** Logic is preserved across rename (Wi‑Fi, TLS fetch from Catalog, HTTPS `/v1/play`, IR driver registry); identifiers and log strings follow Emitter/Catalog vocabulary.

---

## 5. Verification (post-merge)

1. From repo root: `cd catalog && pytest`.
2. `cd firmware/emitter && pio run -e d1_mini` (or the env your `platformio.ini` defines).
3. Skim `PLAYBOOK.md` section 6: checklist still matches live commands and hostnames you deploy (examples may use placeholder domains).
4. Confirm no remaining CI references to `peter/` or `firmware/pete/` on the branch that absorbed this work.

---

## 6. Out of scope (explicitly not required by this rename)

- Changing the public REST path layout (still `/v1/...` unless a separate change does so).
- Database schema migrations for renamed services (SQLite file location may change only if operators relied on the old default path).
- Updating every historical `plans/build/stage-*.md` file: those may still say Peter/Pete until individually revised; this executed plan captures **what landed in git**, not a full doc sweep.
