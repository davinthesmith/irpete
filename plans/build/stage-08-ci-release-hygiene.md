# Stage 8 — CI, automated tests, and release hygiene

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are adding **continuous integration** that runs on every push/PR:

1. **`pytest`** for the `peter/` Python package (no GPIO; use mocks / `TestClient`).
2. **`pio run`** (compile-only) for `firmware/pete/` to catch broken firmware builds.

You will also document **what CI does not cover** (hardware IR, TLS against real Pi, ESP8266 timing).

**Assumption:** Stages **1–7** merged to mainline branch you protect with CI.

---

## 2. Prerequisites

- [ ] `peter/tests/` exists with meaningful tests from Stage 1 (expand if thin).
- [ ] `firmware/pete/` compiles locally with PlatformIO.

---

## 3. Goals

1. Add **GitHub Actions** workflow (`.github/workflows/ci.yml`) or equivalent if using another host.
2. Python job: checkout, cache deps, `pytest`.
3. Firmware job: install PlatformIO CLI, cache `.pio`, `pio run -e d1_mini` (or your env name).
4. Optional: **`ruff`** / **`mypy`** / **`black --check`** if you want standard Python hygiene—keep minimal if time-constrained.
5. README “CI” section: badges (optional), local commands mirroring CI.

---

## 4. Out of scope

- Self-hosted runners with GPIO attached.
- Release signing, SBOM, supply-chain hardening (defer to `plans/later.md` if desired).

---

## 5. Technical design notes (research-backed)

### 5.1 GitHub Actions + PlatformIO

Common pattern:

```yaml
jobs:
  firmware:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/cache@v4
        with:
          path: ~/.platformio
          key: pio-${{ hashFiles('firmware/pete/platformio.ini') }}
      - name: Install PlatformIO
        run: pip install platformio
      - name: Build Pete
        working-directory: firmware/pete
        run: pio run
```

**Reference:** [PlatformIO CI docs](https://docs.platformio.org/en/latest/integration/ci/github-actions.html)

### 5.2 Python matrix

Single version (e.g. **3.11**) is enough for v1; matrix expands later.

### 5.3 pytest paths

Ensure `pytest` discovers tests from repo root via `pyproject.toml` `[tool.pytest.ini_options]` `testpaths = ["peter/tests"]` (adjust to layout).

### 5.4 Secrets in CI

Do **not** add real `IRPETE_API_KEY` to CI; tests should inject ephemeral keys via env in workflow `env:` block for test job only.

---

## 6. Verification (exit criteria)

- [ ] CI green on a clean branch.
- [ ] CI fails when a test is intentionally broken (sanity check once).
- [ ] CI fails when firmware does not compile (sanity check once).
- [ ] README documents local `pytest` + `pio run` parity with CI.

---

## 7. Handoff (project maintenance)

Future features should update:

- [REFERENCE.md](REFERENCE.md) for contract changes.
- [../later.md](../later.md) for deferred ideas.
- CI when adding new packages or envs.

---

## 8. To-do list (Stage 8 execution — start fresh)

- [ ] Add `.github/workflows/ci.yml` (or chosen CI) with Python + PlatformIO jobs.
- [ ] Configure caching for pip and PlatformIO.
- [ ] Ensure `pytest` runs headless with no hardware.
- [ ] Ensure `pio run` uses the intended `[env:…]` target.
- [ ] Add README “Development & CI” section.
- [ ] Optionally add branch protection rules (document in README, repo settings are manual).
- [ ] Run verification §6.

---

## 9. References

- [GitHub Actions](https://docs.github.com/en/actions)
- [PlatformIO CI](https://docs.platformio.org/en/latest/integration/ci/index.html)
- [pytest](https://docs.pytest.org/)
