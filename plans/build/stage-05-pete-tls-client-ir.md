# Stage 5 — Pete: PlatformIO + Wi‑Fi + HTTPS client to Peter + IR `sendRaw`

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are creating **`firmware/pete/`** as a **PlatformIO** project for **ESP8266 Wemos D1 Mini**. Firmware must:

1. Join Wi‑Fi using credentials in **gitignored** `secrets.h` (or `include/secrets.h`).
2. Perform **one** HTTPS `GET` to Peter: `https://peter.toomanyprojects.dev:<port>/v1/signals/{label}` with `Authorization: Bearer …`.
3. Validate server TLS using **embedded CA / chain PEM** (from Stage 3 docs) via **BearSSL** (`setTrustAnchors` / `WiFiClientSecure`).
4. Parse JSON with **ArduinoJson** into structures matching [REFERENCE.md §6](REFERENCE.md).
5. Call **IRremoteESP8266** `IRsend.sendRaw(...)` on pin **D2** ([REFERENCE.md §8](REFERENCE.md)).

**No Pete HTTPS server yet** (Stage 6). Trigger may be **on boot once**, **Serial command**, or **button GPIO**—pick one and document.

**Assumption:** Stages **1–4** done; Peter reachable from Wi‑Fi VLAN; a test label exists in DB.

**Out of scope:** OTA ([`plans/later.md`](../later.md)), SPIFFS secrets, web provisioning portal.

---

## 2. Prerequisites

- [ ] Peter HTTPS reachable from a **phone/laptop on same Wi‑Fi** as Pete will use.
- [ ] `IRPETE_API_KEY` known.
- [ ] CA PEM file path from Stage 3 “Export for Pete” instructions.
- [ ] IR LED circuit on **D2** (with transistor recommended).

---

## 3. Goals

1. Reproducible **`pio run`** build for `d1_mini`.
2. Stable **TLS client** configuration: hostname verification for `peter.toomanyprojects.dev`, correct SNI.
3. **Fetch-then-send** ordering; **no** second TLS session until first completes.
4. **Bench proof:** pressing trigger causes visible IR (camera phone test or IR receiver on second device).

---

## 4. Technical design notes (research-backed)

### 4.1 PlatformIO project skeleton

```ini
[env:d1_mini]
platform = espressif8266
board = d1_mini
framework = arduino
monitor_speed = 115200
lib_deps =
  bblanchon/ArduinoJson @ ^7
  crankyoldgit/IRremoteESP8266 @ ^2.x
```

Tune exact IRremoteESP8266 major version to current stable.

### 4.2 `WiFiClientSecure` + BearSSL anchors

Typical pattern (pseudo-C++):

- `BearSSL::WiFiClientSecure client;`
- `client.setTrustAnchors(&myTA);` where `myTA` is `BearSSLX509` built from embedded PEM.
- `client.connect("peter.toomanyprojects.dev", 8443)`

**Memory:** Keep JSON response small; avoid `DynamicJsonDocument` huge sizes—set capacity based on max `raw_us` from [REFERENCE.md §6](REFERENCE.md) validation limits (mirror Peter’s max length).

**References:**

- ESP8266 Arduino **BearSSL** WiFiClientSecure examples in core docs.
- IRremoteESP8266 `IRsend` examples for `sendRaw`.

### 4.3 `raw_us` type sizes

`sendRaw` historically uses **`uint16_t`** arrays in many examples; Peter may allow larger microsecond values. **Stage 5 must define clipping or require Peter to cap pulses** at 65535 µs—align with Stage 1 validation (prefer capping at ingestion in Peter).

### 4.4 Serial debugging

Use `Serial.printf` guarded by `#ifdef DEBUG` if desired; default **115200 8N1**.

---

## 5. Implementation checklist (suggested order)

1. Create `firmware/pete/platformio.ini` + `src/main.cpp`.
2. Add `include/secrets.h.example` listing `WIFI_SSID`, `WIFI_PASSWORD`, `IRPETE_API_KEY`, `PETER_HOST`, `PETER_PORT`, `PETER_LABEL`, PEM as `extern const char peter_ca_pem[]` or multiline raw string.
3. Implement Wi‑Fi connect with timeout and Serial error messages.
4. Implement TLS GET + HTTP response code checks (401/404/5xx).
5. Parse JSON fields `carrier_hz`, `raw_us`.
6. Initialize `IRsend irsend(kIrLedPin)` with `kIrLedPin = D2` (GPIO4).
7. `irsend.begin();` enable IR PWM.
8. Map JSON → `uint16_t[]` buffer (static max size) + `sendRaw`.
9. Add `firmware/pete/README.md`: wiring, flashing (`pio run -t upload`), serial monitor tips.

---

## 6. Verification (exit criteria)

- [ ] `pio run` succeeds on developer machine (CI may follow in Stage 8).
- [ ] Device associates to Wi‑Fi reliably after power cycle.
- [ ] Successful GET from Peter (log HTTP 200 + parsed pulse count).
- [ ] IR LED visibly blasts (phone camera or IR receiver).
- [ ] Failure modes logged: Wi‑Fi fail, TLS fail, HTTP 401/404, JSON parse fail.

---

## 7. Handoff to Stage 6

Stage 6 adds **BearSSL WiFiServer** / secure web server pattern (or equivalent) for **`POST /v1/play`**. Before starting Stage 6:

- Keep Stage 5 TLS **client** code modular (free functions or small class) so Stage 6 can call “fetchAndSend(label)” from HTTP handler without duplicating TLS setup.

**Risk:** RAM pressure with **both** server + client TLS—Stage 6 plan assumes **single-threaded** handling and **409** busy guard.

---

## 8. To-do list (Stage 5 execution — start fresh)

- [ ] Initialize PlatformIO project under `firmware/pete/`.
- [ ] Add library dependencies (ArduinoJson, IRremoteESP8266).
- [ ] Add secrets template + gitignore rules for `secrets.h`.
- [ ] Implement Wi‑Fi connect.
- [ ] Embed CA trust anchor PEM for Peter chain.
- [ ] Implement HTTPS GET `/v1/signals/{label}` with Bearer header.
- [ ] Parse envelope JSON; handle errors.
- [ ] Implement `sendRaw` on D2 with correct kHz.
- [ ] Document hardware + flash + serial debug in README.
- [ ] Run bench verification §6.

---

## 9. References

- [PlatformIO ESP8266](https://docs.platformio.org/en/latest/platforms/espressif8266.html)
- [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266)
- [ArduinoJson](https://arduinojson.org/)
