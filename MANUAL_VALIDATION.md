# IRPete — manual validation (run once the full application is built)

Run this checklist **after** the sequential build stages in [`plans/build/README.md`](plans/build/README.md) are implemented and CI passes. It covers what **automated tests and CI do not replace**: real DNS, TLS trust chains on devices, GPIO/IR timing, and cold-boot behavior.

**Contract:** [`plans/build/REFERENCE.md`](plans/build/REFERENCE.md) (hostnames, ports, auth, API prefixes).

---

## 1. Preconditions

- [ ] You have the **Raspberry Pi (Peter)** on the LAN with correct **date/time (NTP)**.
- [ ] You have a **second machine** on the same LAN (laptop) with `curl` and `openssl`.
- [ ] **Secrets are not in git** (`.env` on Pi, `secrets.h` or equivalent on Pete when firmware exists).

---

## 2. Peter — DNS and HTTPS

Perform from the **laptop** (not over `-k`; certificate validation must succeed).

Replace `<API_KEY>` with `IRPETE_API_KEY`, `<PORT>` with Peter’s listen port (recommended **8443** per [`peter/README.md`](peter/README.md)), and fix the IP if you use `--resolve`:

```bash
curl -v --resolve peter.toomanyprojects.dev:<PORT>:<PI_LAN_IP> \
  "https://peter.toomanyprojects.dev:<PORT>/v1/health" \
  -H "Authorization: Bearer <API_KEY>"
```

- [ ] **200** response with JSON `{"status":"ok"}` (or equivalent per implementation).
- [ ] Repeat **without** `Authorization`: expect **401**.
- [ ] Repeat with **wrong** Bearer token: expect **401**.

Optional deeper TLS inspection:

```bash
openssl s_client -connect peter.toomanyprojects.dev:<PORT> \
  -servername peter.toomanyprojects.dev </dev/null
```

- [ ] Presented chain matches what you installed (fullchain on disk); **SAN** matches **`peter.toomanyprojects.dev`**.

If verification fails, see troubleshooting in [`peter/README.md`](peter/README.md) (clock skew, incomplete chain, wrong hostname).

---

## 3. Peter — API beyond `/v1/health`

Using the same base URL and Bearer token:

- [ ] **`GET /v1/signals`** returns **200** and a list payload consistent with [`REFERENCE.md`](plans/build/REFERENCE.md) §5.
- [ ] **`POST /v1/signals`** with a valid envelope (then **`GET /v1/signals/{label}`**) round-trips stored JSON.

---

## 4. Peter — IR capture CLI (bench)

On the **Pi**, with TSOP wiring per [`REFERENCE.md`](plans/build/REFERENCE.md) §8:

- [ ] `irpete-capture start` → `stop` → `validate` → `commit --label <label>` completes without error.
- [ ] The same **`IRPETE_DB_PATH`** used by the API shows the new label via **`GET /v1/signals/<label>`** from the laptop.

---

## 5. Peter — systemd and cold boot (after Stage 4)

When a **`systemd`** unit is documented:

- [ ] **`systemctl status`** shows Peter **active** after boot.
- [ ] **`journalctl -u <unit>`** shows startup without interactive prompts; logs go to the journal as intended.

- [ ] **Reboot test:** Pi cold boot → wait for **`network-online`** → HTTPS **`/v1/health`** succeeds from the laptop without manual SSH intervention.

---

## 6. Pete — firmware on hardware (after Stages 5–6)

Skip until the PlatformIO project exists under **`firmware/pete/`** (or the path given in docs).

- [ ] Board joins Wi‑Fi; serial logs show no TLS handshake failures to Peter.
- [ ] Embedded **CA/trust anchor** matches your Peter certificate chain policy ([`peter/README.md`](peter/README.md) “CA PEM for Pete”).
- [ ] **IR LED transmit** can be observed (IR receiver, logic analyzer, or camera against a known remote profile), consistent with [`REFERENCE.md`](plans/build/REFERENCE.md) §8 pin defaults when applicable.

When **`POST /v1/play`** exists on Pete:

- [ ] **`curl`** (or documented client) triggers playback; **409** when busy if implemented.

---

## 7. Repository CI parity (local)

Mirror what CI should run ([`plans/build/stage-08-ci-release-hygiene.md`](plans/build/stage-08-ci-release-hygiene.md)):

```bash
cd peter && pytest
```

- [ ] **All tests pass.**

When firmware is present:

```bash
cd firmware/pete && pio run
```

- [ ] **Firmware builds cleanly.**

---

## 8. Sign-off

- [ ] **Peter:** HTTPS + Bearer + CRUD/capture paths validated on real LAN hardware.
- [ ] **Pete:** TLS client + IR path validated on bench (when firmware ships).
- [ ] **Docs:** Operator paths (`IRPETE_*`, cert locations, troubleshooting) match what you actually deployed.

Record date, Pi OS revision, and firmware git SHA in your deployment notes if you maintain them outside this repo.
