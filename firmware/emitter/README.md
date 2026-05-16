# Emitter — ESP8266 (Wemos D1 Mini)

This firmware joins Wi‑Fi, exposes **HTTPS** on Emitter (**`POST /v1/play`** per [`plans/build/REFERENCE.md`](../../plans/build/REFERENCE.md) §5), **HTTPS GET** an envelope from Catalog (`GET /v1/signals/{label}`), validate TLS with an embedded CA PEM (BearSSL trust anchors), parse JSON per REFERENCE §6, then dispatch the fetched envelope through a **hardware driver registry** (v1: **`IrLedDriver`** with `id` **`ir`**) to **IRremoteESP8266** `sendRaw` on **D2 (GPIO4)**. A **`StubHardwareDriver`** (`id` **`stub`**) is registered for future kinds; **`POST /v1/play`** only selects **`ir`**.

**Doc-only DNS:** you can point **`emitter.toomanyprojects.dev`** at Emitter’s LAN IP (hosts or LAN DNS) so curl examples stay stable; the board still uses DHCP unless you pin it ([REFERENCE.md](REFERENCE.md) §3).

## Prerequisites

- PlatformIO ([install](https://docs.platformio.org/en/latest/core/installation.html)); this repo often uses a local venv: `python3 -m venv .venv && . .venv/bin/activate && pip install platformio`.
- Catalog reachable at `https://catalog.toomanyprojects.dev:<port>` from the same LAN (split‑horizon DNS or hosts entry as needed).
- `IRPETE_API_KEY` matching Catalog’s environment (`Authorization: Bearer` — same secret for Catalog API and Emitter’s **`POST /v1/play`**).
- TLS material for **Emitter’s HTTPS server** (leaf or wildcard PEM + private key in `secrets.h`; see template).
- A signal row already stored for any label you play (e.g. via `POST /v1/signals` or the capture CLI).

## Secrets and TLS

1. Copy `include/secrets.h.example` to `include/secrets.h` (or let the first `pio run` copy it via `extra_scripts/prep_secrets.py`).
2. Set `WIFI_SSID`, `WIFI_PASSWORD`, `IRPETE_API_KEY`, `CATALOG_HOST`, `CATALOG_PORT`, and **`EMITTER_SERVER_CERT_PEM` / `EMITTER_SERVER_PRIVATE_KEY_PEM`** (replace the bundled **development** self-signed pair before production).
3. **`CATALOG_CA_PEM`:** Trust anchor for Catalog’s HTTPS certificate (often Let’s Encrypt issuer / root — see REFERENCE §3).
4. **`EMITTER_HTTPS_PORT`:** HTTPS listen port for Emitter (default **8443**, aligned with REFERENCE §9).
5. **`EMITTER_SIMULATE_BUSY_MS`:** Optional milliseconds **before** contacting Catalog: during this window the firmware polls for **queued** HTTPS clients and answers them with **409 Conflict** so you can demonstrate overlapping `curl` requests on the bench. Use **0** in normal operation.

`include/secrets.h` is gitignored.

## Pinout (IR output — default)

| Signal / node | Wemos D1 Mini pin | ESP8266 GPIO |
|---------------|-------------------|--------------|
| IR driver output (to NPN base **via** base resistor, see below) | **D2** | **GPIO4** |
| GND | G | — |
| 3V3 | 3V3 | — (logic supply only; IR LED current comes from **5V** or a dedicated rail, not from the 3V3 pin) |

Do **not** drive a high‑current IR LED directly from **D2**; use an NPN switch as below.

## IR circuit (NPN + base resistor + IR LED)

Use a common small‑signal NPN such as **2N2222**, **2N3904**, or **BC337** in a low‑side switch arrangement: emitter to GND, collector to the IR LED cathode (or anode depending on polarity — match your LED), LED current limited by **`R_led`** from **`V_led`** (often **5V** from USB/regulator when the board is USB‑powered).

ASCII (one valid topology; verify LED polarity on your part):

```
         V_led (e.g. +5V)
              |
             +|+
         R_led  (e.g. 47 Ω–100 Ω — see math)
              |
              +-------> IR LED anode (+)
              |
         IR LED cathode (-)
              |
              C
         B   /  NPN (2N2222 / 2N3904)
  D2 --[Rb]--B     E
              |     |
             GND    GND
```

- **`Rb` (base resistor):** typical **330 Ω–1 kΩ** from **D2** to the base so GPIO current stays small while saturating the transistor for the expected collector current.
- **`R_led` template:** \(I \approx (V_{\mathrm{led}} - V_f) / R\) where \(V_f\) is the IR LED forward voltage (often ~1.2–1.5 V) and \(V_{\mathrm{led}}\) is your LED supply. Example: **5 V** supply, **\(V_f = 1.3\) V**, **\(R = 68\,\Omega\)** → ~**55 mA** (order‑of‑magnitude; check transistor max **\(I_C\)**, LED max current, and heat).

**Eye safety:** IR remotes are bright in phone cameras; **do not stare into the LED** at close range. Treat unknown peak wavelengths/intensities as hazardous until you characterize them.

## Build and flash

```bash
cd firmware/emitter
pio run
pio run -t upload
pio device monitor  # 115200 8N1
```

## Runtime behavior

- After Wi‑Fi connects, firmware starts **BearSSL `WiFiServerSecure`** on **`EMITTER_HTTPS_PORT`** (default **8443**).
- **`POST /v1/play`** with JSON body and header `Authorization: Bearer <IRPETE_API_KEY>`:
  - **Body:** required **`label`**. Optional **`kind`**: string, default **`"ir"`** (case‑insensitive). Any other value → **400** with `{"error":"unknown_kind"}`. Non‑string **`kind`** or empty/oversized string → **400** `invalid_kind`.
  - **401** — missing or wrong Bearer.
  - **404** — Catalog returned **404** for that label (unknown label).
  - **409** — another play is in progress; **or** (during `EMITTER_SIMULATE_BUSY_MS`) a second TLS client completed handshake while the first request is still in the busy window.
  - **503** — TLS/HTTP transport failure or Catalog **5xx** when fetching the envelope.
  - **502** — Catalog returned **401** to Emitter’s fetch (misconfigured keys), JSON/envelope invalid upstream.
  - **200** — `{"ok":true}` after the **`ir`** driver completes **`sendRaw`**.
- Request bodies larger than **384 bytes** are rejected (**400**).
- By default (`EMITTER_TRIGGER_ON_BOOT` **1** in `src/main.cpp`), after boot the board still performs **one** fetch + IR play for **`CATALOG_LABEL`** (sanity check).
- Serial: press **`s`** or **Enter** to replay **`CATALOG_LABEL`** via Catalog + IR (same pipeline as `/v1/play`, without HTTPS).

### Serial phases (HTTPS success path)

On success you should see: **`HTTPS in: POST /v1/play`** → **`phase: TLS out (Catalog fetch)`** → **`Catalog fetch: ok`** → **`HTTP 200: pulses=`** → **`phase: IR sendRaw`** → **`IR: sendRaw complete`** → **`HTTPS out: 200`**.

## Operator curl (laptop → Emitter → Catalog → IR)

Replace IP, port, key, and label. Use **`--cacert`** with the PEM that validates Emitter’s **server** certificate (the same chain or leaf you configured for curl trust — for the bundled self-signed example cert, use that cert file as **`--cacert`**).

```bash
curl -v --cacert emitter-server-cert.pem \
  --resolve emitter.toomanyprojects.dev:8443:192.168.1.50 \
  -H "Authorization: Bearer $IRPETE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label":"tv_power","kind":"ir"}' \
  https://emitter.toomanyprojects.dev:8443/v1/play
```

Omitting **`kind`** is equivalent to **`"ir"`**.

- Wrong Bearer → **401**.
- Unknown label (Catalog has no row) → **404** JSON `unknown_label`.
- Unknown **`kind`** (not `ir`) → **400** JSON `unknown_kind`.

### Overlapping requests (409)

With **`EMITTER_SIMULATE_BUSY_MS`** set to e.g. **3000**, start a long first request (or rely on the busy window), then within that window run a **second** `curl`: the second should receive **409** with body `{"error":"busy"}` while the first still completes normally after the window.

Without the simulate window, a second client may **queue** until the first finishes (ESP8266 serves one accepted TLS stream at a time in this sketch); the simulate hook exists so overlap can be demonstrated reliably on hardware.

## HIL checklist (hardware-in-the-loop)

Run on a bench with **Catalog** up and **Emitter** on Wi‑Fi (see also repo root [`README.md`](../../README.md)):

1. **NEC-like remote** (common TV): capture on Catalog (e.g. `irpete-capture` or `POST /v1/signals`), play via Emitter; device responds.
2. **Long RAW / toggle-style remote:** envelope length near the configured **max** (REFERENCE: **512** `raw_us` elements) still plays (validates RAM sizing).
3. **Rapid repeat:** fire the same label **10×** sequentially; no heap corruption or resets (watch Serial).
4. **Auth negative:** remove Bearer temporarily in curl; expect **401**.
5. **Busy negative:** trigger overlapping requests; expect **409** on the second (use **`EMITTER_SIMULATE_BUSY_MS`** if needed).
6. **Power cycle Emitter:** first play after reboot succeeds without manually restarting Catalog.

CI / repo tests cover **`pio run`** and source-level contracts ([`catalog/tests/test_firmware_emitter_contract.py`](../../catalog/tests/test_firmware_emitter_contract.py)); they do **not** replace IR LED or LAN TLS bench checks ([`REFERENCE.md`](../../plans/build/REFERENCE.md) §11).

## Module layout

| Module | Role |
|--------|------|
| `src/catalog_tls_client.{h,cpp}` | BearSSL client → `GET /v1/signals/{label}` |
| `src/emitter_https_play.{h,cpp}` | BearSSL server → `POST /v1/play`, Bearer, optional **`kind`**, busy **409** |
| `src/hardware_driver.{h,cpp}` | `HardwareDriver` interface + `registerDriver` / `getDriver` |
| `src/ir_led_driver.{h,cpp}` | Driver **`ir`**: envelope → `sendRaw` |
| `src/stub_hardware_driver.h` | Reserved driver **`stub`** (not used by v1 play) |
| `src/main.cpp` | Wi‑Fi, `IRsend`, registry init, `playPipeline`, HTTPS poll loop |
