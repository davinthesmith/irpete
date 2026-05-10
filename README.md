# IRPete

IR capture and replay stack: **Peter** (Raspberry Pi HTTPS API + SQLite) and **Pete** (ESP8266 HTTPS client/server + IR). Authoritative contracts live in [`plans/build/REFERENCE.md`](plans/build/REFERENCE.md).

- **Peter (Python):** [`peter/README.md`](peter/README.md)
- **Pete (firmware):** [`firmware/pete/README.md`](firmware/pete/README.md)

## Pete hardware-in-the-loop (HIL) checklist

Operator runs on a bench with Peter up and Pete on Wi‑Fi:

1. **NEC-like remote** (common TV): capture on Peter (Stage 2), play via Pete; device responds.
2. **Long RAW / toggle-style remote:** ensure envelope length near your configured max still plays (validates RAM sizing).
3. **Rapid repeat:** fire same label **10×** sequentially; no heap corruption / resets (watch Serial).
4. **Auth negative:** remove Bearer temporarily in curl; expect **401**.
5. **Busy negative:** trigger overlapping requests; expect **409** on second.
6. **Power cycle Pete:** first play after reboot succeeds without manual Peter restart.

Details, pinout, IR transistor circuit, and curl examples: [`firmware/pete/README.md`](firmware/pete/README.md).

## Development & CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request:

1. **Python** — install `peter/` in editable mode with dev extras, then `pytest` from `peter/` (FastAPI `TestClient`, no GPIO). `IRPETE_API_KEY` is set to a throwaway value in the workflow; tests still rely on fixtures and `monkeypatch` where needed.
2. **Firmware** — install the PlatformIO CLI, cache `~/.platformio`, then `pio run -e d1_mini` under `firmware/pete/` (compile-only). `extra_scripts/prep_secrets.py` creates `include/secrets.h` from the example when missing, so a clean clone builds in CI.

Local parity:

```bash
# Peter
cd peter && python -m pip install -e ".[dev]" && pytest -q

# Pete
cd firmware/pete && pip install platformio && pio run -e d1_mini
```

With `pio` on your PATH, `pytest` also runs `test_pio_run_succeeds_when_platformio_available` in `peter/tests/test_firmware_pete_contract.py` (full compile from the Python job); without `pio`, that test is skipped — the dedicated firmware job still compiles on every CI run.

**What CI does not cover:** real IR LED/TSOP hardware, TLS handshakes against a live Raspberry Pi, ESP8266 timing on air, Wi‑Fi provisioning, and operator HIL steps above. Use [`firmware/pete/README.md`](firmware/pete/README.md) for bench validation.

**Branch protection:** enabling “required status checks” for the CI workflow is done in the GitHub repo settings (this repo cannot apply that from code).
