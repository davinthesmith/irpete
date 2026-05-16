# Pete — ESP8266 (Wemos D1 Mini)

Stage 6 firmware: join Wi‑Fi, expose **HTTPS** on Pete (**`POST /v1/play`** per [`plans/build/REFERENCE.md`](../../plans/build/REFERENCE.md) §5), **HTTPS GET** an envelope from Peter (`GET /v1/signals/{label}`), validate TLS with an embedded CA PEM (BearSSL trust anchors), parse JSON per REFERENCE §6, then transmit with **IRremoteESP8266** `sendRaw` on **D2 (GPIO4)**.

## Prerequisites

- PlatformIO ([install](https://docs.platformio.org/en/latest/core/installation.html)); this repo often uses a local venv: `python3 -m venv .venv && . .venv/bin/activate && pip install platformio`.
- Peter reachable at `https://peter.toomanyprojects.dev:<port>` from the same LAN (split‑horizon DNS or hosts entry as needed).
- `IRPETE_API_KEY` matching Peter’s environment (`Authorization: Bearer` — same secret for Peter API and Pete’s **`POST /v1/play`**).
- TLS material for **Pete’s HTTPS server** (leaf or wildcard PEM + private key in `secrets.h`; see template).
- A signal row already stored for any label you play (e.g. via `POST /v1/signals` or the capture CLI).

## Secrets and TLS

1. Copy `include/secrets.h.example` to `include/secrets.h` (or let the first `pio run` copy it via `extra_scripts/prep_secrets.py`).
2. Set `WIFI_SSID`, `WIFI_PASSWORD`, `IRPETE_API_KEY`, `PETER_HOST`, `PETER_PORT`, and **`PETE_SERVER_CERT_PEM` / `PETE_SERVER_PRIVATE_KEY_PEM`** (replace the bundled **development** self-signed pair before production).
3. **`PETER_CA_PEM`:** Trust anchor for Peter’s HTTPS certificate (often Let’s Encrypt issuer / root — see REFERENCE §3).
4. **`PETE_HTTPS_PORT`:** HTTPS listen port for Pete (default **8443**, aligned with REFERENCE §9).
5. **`PETE_SIMULATE_BUSY_MS`:** Optional milliseconds **before** contacting Peter: during this window the firmware polls for **queued** HTTPS clients and answers them with **409 Conflict** so you can demonstrate overlapping `curl` requests on the bench. Use **0** in normal operation.

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

- After Wi‑Fi connects, firmware starts **BearSSL `WiFiServerSecure`** on **`PETE_HTTPS_PORT`** (default **8443**).
- **`POST /v1/play`** with JSON `{"label":"<name>"}` and header `Authorization: Bearer <IRPETE_API_KEY>`:
  - **401** — missing or wrong Bearer.
  - **404** — Peter returned **404** for that label (unknown label).
  - **409** — another play is in progress; **or** (during `PETE_SIMULATE_BUSY_MS`) a second TLS client completed handshake while the first request is still in the busy window.
  - **503** — TLS/HTTP transport failure or Peter **5xx** when fetching the envelope.
  - **502** — Peter returned **401** to Pete’s fetch (misconfigured keys), JSON/envelope invalid upstream.
  - **200** — `{"ok":true}` after IR `sendRaw`.
- Request bodies larger than **384 bytes** are rejected (**400**).
- By default (`PETE_TRIGGER_ON_BOOT` **1** in `src/main.cpp`), after boot the board still performs **one** fetch + **sendRaw** for **`PETER_LABEL`** (Stage 5-style sanity check).
- Serial: press **`s`** or **Enter** to replay **`PETER_LABEL`** via Peter + IR (same pipeline as `/v1/play`, without HTTPS).

### Serial phases (Stage 6 verification)

On success you should see a clear sequence: **`HTTPS in: POST /v1/play`** → **`phase: TLS out (Peter fetch)`** → **`Peter fetch: ok`** → **`phase: IR sendRaw`** → **`HTTPS out: 200`** (with **`HTTP 200: pulses=`** from the client stack).

## Operator curl (laptop → Pete → Peter → IR)

Replace IP, port, key, and label. Use **`--cacert`** with the PEM that validates Pete’s **server** certificate (the same chain or leaf you configured for curl trust — for the bundled self-signed example cert, use that cert file as **`--cacert`**).

```bash
curl -v --cacert pete-server-cert.pem \
  --resolve pete.toomanyprojects.dev:8443:192.168.1.50 \
  -H "Authorization: Bearer $IRPETE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label":"tv_power"}' \
  https://pete.toomanyprojects.dev:8443/v1/play
```

- Wrong Bearer → **401**.
- Unknown label (Peter has no row) → **404** JSON `unknown_label`.

### Overlapping requests (409)

With **`PETE_SIMULATE_BUSY_MS`** set to e.g. **3000**, start a long first request (or rely on the busy window), then within that window run a **second** `curl`: the second should receive **409** with body `{"error":"busy"}` while the first still completes normally after the window.

Without the simulate window, a second client may **queue** until the first finishes (ESP8266 serves one accepted TLS stream at a time in this sketch); the simulate hook exists so Stage 6 **§6 overlap** can be demonstrated reliably on hardware.

## Bench verification (Stages 5–6)

Complete on hardware when Peter is live:

1. After power cycle, device associates to Wi‑Fi (serial shows IP).
2. **`curl`** `POST /v1/play` returns **200** and IR flashes; serial shows TLS + IR phases.
3. Wrong Bearer → **401**; bogus label → **404** (if absent on Peter).
4. With **`PETE_SIMULATE_BUSY_MS` > 0**, overlapping curls demonstrate **409**.

CI / repo tests cover **`pio run`** and source-level contracts ([`peter/tests/test_firmware_pete_contract.py`](../../peter/tests/test_firmware_pete_contract.py)); they do **not** replace IR LED or LAN TLS bench checks ([`REFERENCE.md`](../../plans/build/REFERENCE.md) §11).

## Module layout

| Module | Role |
|--------|------|
| `src/peter_tls_client.{h,cpp}` | BearSSL client → `GET /v1/signals/{label}` |
| `src/pete_https_play.{h,cpp}` | BearSSL server → `POST /v1/play`, busy/auth/path handling |
| `src/main.cpp` | Wi‑Fi, IR pin, `playPipeline`, HTTPS poll loop |

Stage 7 may refactor IR sending behind a driver interface without changing this HTTP surface.
