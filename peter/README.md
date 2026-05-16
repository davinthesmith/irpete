# IRPete — Peter (Stages 1–4)

Peter exposes a versioned JSON **envelope** API backed by **SQLite (WAL)**. Authentication is a single shared **`IRPETE_API_KEY`** passed as `Authorization: Bearer <token>` on **every** `/v1` route, including **`GET /v1/health`**.

Stage 2 adds the **`irpete-capture`** CLI on the Raspberry Pi: record TSOP pulse timings (RAM until `stop`), then **`validate`** / **`preview`** / **`commit`** using the **same** Pydantic rules and SQLite upsert as `POST /v1/signals`.

Stage 3 adds **HTTPS on the LAN** via Uvicorn **`ssl_certfile` / `ssl_keyfile`** when **`IRPETE_TLS_CERTFILE`** and **`IRPETE_TLS_KEYFILE`** are set (paths to PEM files). Leave both unset for **local HTTP only** (`127.0.0.1`, default port **8000**).

Stage 4 adds a **systemd** unit template so Peter starts **after the network is online**, **restarts on failure**, and logs to **journald** (no secrets in the unit file—use **`/etc/irpete/peter.env`**).

Shared contract: [`plans/build/REFERENCE.md`](../plans/build/REFERENCE.md).

**Auth errors:** missing or wrong `Authorization: Bearer` returns **401 Unauthorized** (with `WWW-Authenticate: Bearer`).

## Stage 1 — development run (HTTP, no TLS)

From this directory (`peter/`):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # edit IRPETE_API_KEY
export $(grep -v '^#' .env | xargs)   # or use direnv / manual export
python -m irpete.main
```

Equivalent with uvicorn factory (loads settings from the environment):

```bash
export IRPETE_API_KEY=dev-secret
uvicorn irpete.app:create_app --factory --host 127.0.0.1 --port 8000
```

The API listens on **`IRPETE_HOST` / `IRPETE_PORT`** (defaults **`127.0.0.1:8000`**). SQLite defaults to **`data/irpete.db`** under `peter/` when **`IRPETE_DB_PATH`** is unset.

## Stage 3 — HTTPS on the LAN (`peter.toomanyprojects.dev`)

Production-style TLS is a **deployment** concern: the FastAPI app is unchanged; Uvicorn loads **`IRPETE_TLS_CERTFILE`** (fullchain PEM) and **`IRPETE_TLS_KEYFILE`** (private key PEM). Recommended listen port is **8443** so the process does not need **`CAP_NET_BIND_SERVICE`** for port **443**.

### Prerequisites

- **DNS:** An **A** (and optionally **AAAA**) record for **`peter.toomanyprojects.dev`** pointing at the Raspberry Pi’s **LAN** address (split-horizon DNS is fine).
- **Certificates:** A wildcard **`*.toomanyprojects.dev`** or a dedicated leaf whose **SAN** includes **`peter.toomanyprojects.dev`**. Install **fullchain** + **private key** on the Pi (example paths: `/etc/irpete/fullchain.pem`, `/etc/irpete/privkey.pem`).
- **Permissions:** `chmod 600` on the private key; restrict directory listing as usual.
- **Clock:** TLS validation fails if the Pi’s clock is wrong—use **NTP** (`timedatectl`).

### Environment (HTTPS)

Set **`IRPETE_API_KEY`**, **`IRPETE_TLS_CERTFILE`**, **`IRPETE_TLS_KEYFILE`**, and typically:

```bash
export IRPETE_HOST=0.0.0.0
export IRPETE_PORT=8443
```

Optional: **`IRPETE_DISABLE_OPENAPI=1`** to disable **`/docs`**, **`/redoc`**, and **`/openapi.json`** on networks where Swagger UI is unnecessary.

### Run with TLS

From `peter/` after `pip install -e ".[dev]"` and loading secrets from `.env`:

```bash
./scripts/run-peter-https.sh
```

Or explicitly:

```bash
export IRPETE_API_KEY=…
export IRPETE_TLS_CERTFILE=/etc/irpete/fullchain.pem
export IRPETE_TLS_KEYFILE=/etc/irpete/privkey.pem
export IRPETE_HOST=0.0.0.0
export IRPETE_PORT=8443
python -m irpete.main
```

### Verify from another machine (full TLS verification, no `-k`)

Replace `<token>` with **`IRPETE_API_KEY`** (and **`8443`** if that is your listen port):

```bash
curl -v --resolve peter.toomanyprojects.dev:8443:192.168.x.x \
  "https://peter.toomanyprojects.dev:8443/v1/health" \
  -H "Authorization: Bearer <token>"
```

If DNS already resolves to the Pi on your LAN, omit **`--resolve`**. Expect **`HTTP/1.1 200`** (or HTTP/2) and JSON **`{"status":"ok"}`**.

Wrong or missing Bearer:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://peter.toomanyprojects.dev:8443/v1/health"
# expect 401
```

### Troubleshooting TLS

| Symptom | Likely cause |
|--------|----------------|
| `certificate verify failed` | Wrong hostname vs SAN, incomplete chain on disk, or clock skew on client/Pi |
| Connection refused | Firewall, wrong **`IRPETE_HOST`/`PORT`**, or service not running |

Inspect the certificate chain:

```bash
openssl s_client -connect peter.toomanyprojects.dev:8443 -servername peter.toomanyprojects.dev </dev/null
```

### CA PEM for Pete firmware (Stage 5)

ESP8266/BearSSL needs a **trust anchor**—usually the **issuing CA** PEM (not the leaf). Operators keep a copy as e.g. **`certs/peter-ca.pem`** (gitignored); Pete embeds bytes in **`secrets.h`** or SPIFFS later.

**If you already have the issuer CA file from your PKI**, copy it verbatim to **`peter-ca.pem`**.

**If you only have the server fullchain** (leaf + intermediates), inspect PEM subjects and extract the issuer certificate your clients trust:

```bash
openssl crl2pkcs7 -nocrl -certfile /etc/irpete/fullchain.pem \
  | openssl pkcs7 -print_certs -noout
```

Sanity check issuer vs subject on the leaf:

```bash
openssl x509 -in /etc/irpete/fullchain.pem -noout -issuer -subject
```

Document which PEM you embedded so rotations stay predictable: Pete trusts the **CA**, so **leaf rotation** does not require a firmware change as long as the new leaf chains to the same anchor.

## Stage 4 — systemd service (boot, restart, journald)

Peter runs as a **system** service so it can bind **`IRPETE_PORT`** (recommended **8443**), read **`/etc/irpete/`** TLS material, and start without an interactive shell.

### Unit template and environment file

In the repo:

- [`deploy/systemd/irpete-peter.service`](deploy/systemd/irpete-peter.service) — copy to **`/etc/systemd/system/`** and adjust **`WorkingDirectory`** + **`ExecStart`** (venv **`python`** that has `pip install -e .`).
- [`deploy/peter.env.example`](deploy/peter.env.example) — keys to place in **`/etc/irpete/peter.env`** (no committed secrets).

### Install on Raspberry Pi OS

1. Install the app and venv under a stable path (example **`/opt/irpete/peter`**):

   ```bash
   sudo mkdir -p /opt/irpete
   sudo rsync -a ./peter/ /opt/irpete/peter/
   cd /opt/irpete/peter
   sudo python3 -m venv .venv
   sudo .venv/bin/pip install -e .
   ```

2. Create **`/etc/irpete/peter.env`** from **`deploy/peter.env.example`**, set **`IRPETE_API_KEY`**, TLS paths, **`IRPETE_HOST=0.0.0.0`**, **`IRPETE_PORT=8443`**, and optionally **`IRPETE_DB_PATH`** (absolute path is best for reboot stability).

   ```bash
   sudo install -d -m 0755 /etc/irpete
   sudo install -m 0600 /path/to/your/peter.env /etc/irpete/peter.env
   sudo chown root:root /etc/irpete/peter.env
   ```

   Ensure the **private key** PEM is **`chmod 600`** and readable by the user running the service (root by default in the template).

3. Edit the copied unit so **`WorkingDirectory`** and **`ExecStart`** match step 1, then enable:

   ```bash
   sudo cp /opt/irpete/peter/deploy/systemd/irpete-peter.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now irpete-peter
   ```

4. Confirm **`active (running)`**:

   ```bash
   systemctl status irpete-peter --no-pager
   ```

### Logs

Follow Uvicorn and Python logs:

```bash
journalctl -u irpete-peter -f
```

Recent boot:

```bash
journalctl -u irpete-peter -b --no-pager
```

Expect **`Application startup complete`** (Uvicorn) and no repeated TLS file errors.

### `network-online.target` (DNS readiness)

The unit is ordered **after** **`network-online.target`** so systemd waits for a configured “network is up” waiter. On **Wi‑Fi‑only** Pis, ensure your image enables **`systemd-networkd-wait-online.service`** or **`NetworkManager-wait-online.service`** as appropriate; otherwise DNS for **`peter.toomanyprojects.dev`** may not be ready immediately. **Ethernet** is simpler for headless reliability.

### Cold reboot acceptance (operator)

After **`systemctl enable --now irpete-peter`** works once:

1. **`sudo reboot`** (or power cycle).
2. Within **~1–3 minutes** (typical LAN + DHCP), from another host:

   ```bash
   curl -sS --resolve peter.toomanyprojects.dev:8443:192.168.x.x \
     "https://peter.toomanyprojects.dev:8443/v1/health" \
     -H "Authorization: Bearer <IRPETE_API_KEY>"
   ```

   Expect **`{"status":"ok"}`** (or your app’s health JSON) and **HTTP 200**.

3. On the Pi, **`systemctl status irpete-peter`** shows **active (running)**.

### Crash recovery

To confirm **`Restart=always`**, after the service is healthy:

```bash
sudo kill -9 "$(pgrep -f 'irpete.main' | head -1)"
```

Within a few seconds, **`systemctl status irpete-peter`** should show a fresh PID and **`journalctl -u irpete-peter -n 20`** should show a new startup.

### Troubleshooting (systemd)

| Symptom | Likely cause |
|--------|----------------|
| Service starts but **`curl` fails hostname** | DNS not ready yet (`network-online` waiter missing on Wi‑Fi), or split-horizon DNS not pointing at the Pi |
| **`status=203/EXEC`** or **`No such file`** in journal | Wrong **`ExecStart`** path (venv python moved or not installed) |
| **SQLite / relative paths wrong** | **`WorkingDirectory`** does not match the tree where **`data/`** or **`IRPETE_DB_PATH`** was intended |
| **TLS / permission denied** | Key or cert path wrong, or PEM not readable by the service user; check **`journalctl -u irpete-peter`** |
| **401 from health** | Missing **`IRPETE_API_KEY`** in **`/etc/irpete/peter.env`** or wrong Bearer on the client |

## Stage 2 — manual IR capture CLI (`irpete-capture`)

After `pip install -e ".[dev]"` (or `pip install -e .`), the console script **`irpete-capture`** is available.

### Hardware (TSOP)

- **BCM GPIO 18** (physical pin 12 on the 40-pin header) is the default **data** line from the TSOP demodulator output (see REFERENCE §8).
- Wire **VCC/GND** per your module’s datasheet (3V3 vs 5V modules differ).
- **Permissions:** GPIO access on Raspberry Pi OS usually requires membership in the **`gpio`** group (then re-login) or running capture as root. Prefer `gpio` membership over blanket `sudo`.

### Recording backend

- **Preferred:** **`lgpio`** (Bookworm on Pi 4/5) for edge timestamps. Install the OS/Python package that provides `import lgpio` (e.g. `python3-lgpio` on Raspberry Pi OS).
- **Fallbacks:** **`pigpio`** is common on older images; Pi 5 support varies—verify before relying on it. **`RPi.GPIO`** without dedicated edge timing is a poor fit for IR pulse capture.

### Training workflow (example)

Use one shell for Peter’s API (optional, for `GET` verification) and another for capture, or commit offline and query later.

```bash
# Terminal A — HTTP API (Stage 1 dev)
export IRPETE_API_KEY=dev-secret
export IRPETE_DB_PATH=/home/pi/irpete/data/irpete.db   # same DB the CLI will use
python -m irpete.main
```

```bash
# Terminal B — capture (Pi with TSOP on BCM 18)
export IRPETE_DB_PATH=/home/pi/irpete/data/irpete.db
irpete-capture start --pin 18 --carrier-hz 38000
# Press a remote button, then:
irpete-capture stop
irpete-capture preview
irpete-capture validate
irpete-capture commit --label my_button
```

- **`start`** spawns a background recorder process; **`stop`** sends **SIGTERM**, writes **`candidate.json`** (pulse timings + `carrier_hz`) under the state directory — **no SQLite write yet**.
- **`validate`** runs the same envelope validation as **`POST /v1/signals`** (including mark-first normalization).
- **`commit`** upserts into SQLite by **`label`**; use the same **`IRPETE_DB_PATH`** as the API process so **`GET /v1/signals/{label}`** returns the new envelope.
- Override state dir with **`--state-dir`** if you need multiple isolated sessions (default: `XDG_STATE_HOME/irpete/capture` or `~/.local/state/irpete/capture`).
- **Pi 5:** if `start` fails to open GPIO, try **`--gpio-chip 4`** (chip index depends on the board).

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Envelope semantics (Stages 1–4)

- **`POST /v1/signals`** **upserts by `label`** (same label replaces the stored envelope).
- **`raw_us` mark-first normalization:** IRremoteESP8266 `sendRaw` expects the first entry to be a **mark**. On POST, if the first duration is **greater than 50 ms**, it is treated as a leading idle gap and **removed once** so the stored array starts with a mark-oriented timing sequence. Values must fit **uint16** on the wire (1–65535 µs per element). Length is capped at **512** elements for v1.

## Schema migration (v1)

DDL lives in [`schema.sql`](schema.sql) and is applied automatically on startup via `irpete.repository.init_db`. For manual provisioning, run that SQL against your SQLite file once.
