# IRPete — deferred / later

Items explicitly out of scope for the first implementation pass, or follow-ups worth tracking.

## Firmware (Pete)

- **OTA updates** — flash over USB for v1; add signed OTA partition + HTTPS OTA URL + rollback later.
- **WiFi captive portal / WiFiManager** — if hardcoded `secrets.h` becomes painful for non-developers.
- **BLE or Improv Wi‑Fi** provisioning — alternative to portal for headless setup.
- **Factory reset** — GPIO long-press or serial command to clear Wi‑Fi / API key without reflash.
- **mDNS advertisement** — `pete.local` in addition to static DNS if you want zero-config discovery on some networks.

## Peter (host / capture)

- **HTTP “arm capture” API** — optional remote trigger instead of CLI-only manual sessions.
- **Rate limiting** — if Peter is ever exposed beyond trusted LAN clients.
- **Separate read vs write API keys** — if you later want least-privilege (Pete read-only, admin laptop write).

## IR / hardware

- **Raw IR learner path** (pre-demodulator) — for exotic protocols where TSOP-learned timings are insufficient.
- **Multi-signal macros** — one label fires a sequence of stored signals with delays.
- **IR receive on Pete** — local learning without Peter (usually not needed if Peter is canonical).

## Ops / product

- **Metrics export** — Prometheus / structured logs for play counts and TLS errors.
- **Automated SQLite backup** — timer unit pushing copies to NAS or object storage.
- **Home Assistant integration** — REST entity or blueprint calling Pete’s `/v1/play`.

## Docs / CI

- **Hardware-in-the-loop CI** — only where you add a self-hosted runner with GPIO; most repos stay mock-only.
