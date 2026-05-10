# Pete — ESP8266 (Wemos D1 Mini)

Stage 5 firmware: join Wi‑Fi, **HTTPS GET** a signal envelope from Peter (`GET /v1/signals/{label}`), validate TLS with an embedded CA PEM (BearSSL trust anchors), parse JSON per [`plans/build/REFERENCE.md`](../plans/build/REFERENCE.md) §6, then transmit with **IRremoteESP8266** `sendRaw` on **D2 (GPIO4)**.

## Prerequisites

- PlatformIO ([install](https://docs.platformio.org/en/latest/core/installation.html)); this repo often uses a local venv: `python3 -m venv .venv && . .venv/bin/activate && pip install platformio`.
- Peter reachable at `https://peter.toomanyprojects.dev:<port>` from the same LAN (split‑horizon DNS or hosts entry as needed).
- `IRPETE_API_KEY` matching Peter’s environment (HTTP `Authorization: Bearer` — see `peter_tls_client.cpp`).
- A signal row already stored for the label you request (e.g. via `POST /v1/signals` or the capture CLI).

## Secrets and TLS

1. Copy `include/secrets.h.example` to `include/secrets.h` (or let the first `pio run` copy it via `extra_scripts/prep_secrets.py`).
2. Set `WIFI_SSID`, `WIFI_PASSWORD`, `IRPETE_API_KEY`, and optionally `PETER_HOST`, `PETER_PORT`, `PETER_LABEL`.
3. **`PETER_CA_PEM`:** The example embeds **ISRG Root X1** (public Let’s Encrypt anchor). If Peter’s certificate chain is signed by another CA, replace this PEM with the issuer / chain from Stage 3 “Export for Pete” (see [`REFERENCE.md`](../plans/build/REFERENCE.md) §3).

`include/secrets.h` is gitignored.

## Wiring (IR LED)

| Node | D1 Mini |
|------|---------|
| IR LED circuit (via transistor + resistor, see Stage 7 docs) | **D2** → **GPIO4** |

Do **not** drive a bare IR LED directly from GPIO; use a transistor-level shifted circuit for range and safety.

## Build and flash

```bash
cd firmware/pete
pio run
pio run -t upload
pio device monitor  # 115200 8N1
```

## Runtime behavior

- On boot, firmware connects to Wi‑Fi, then (by default) performs **one** fetch + **sendRaw** (`PETE_TRIGGER_ON_BOOT` is `1` in `src/main.cpp`).
- Over serial, press **`s`** or **Enter** to repeat fetch + IR (no overlapping TLS fetch until the previous completes).

Logs cover failure modes: Wi‑Fi timeout, TLS/HTTP errors, **401** / **404**, JSON/envelope validation errors, and success (**HTTP 200** + pulse count).

## Bench verification (Stage 5 exit criteria)

Complete on hardware when Peter is live:

1. After power cycle, device associates to Wi‑Fi (serial shows IP).
2. Serial shows **HTTP 200** and a plausible pulse count.
3. IR activity is visible (phone camera pointed at LED, or a second receiver).

CI covers **`pio run`** when PlatformIO is installed; it does **not** replace this hardware checklist ([`REFERENCE.md`](../plans/build/REFERENCE.md) §11).

## Module layout (Stage 6 handoff)

HTTPS fetch + JSON parsing live in `src/peter_tls_client.{h,cpp}` so a future **`POST /v1/play`** handler can call `peter::fetchSignalEnvelope` without duplicating BearSSL setup.
