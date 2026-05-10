# Stage 4 — Peter: systemd service + boot ordering + cold reboot acceptance

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are packaging Peter’s HTTPS Uvicorn process as a **`systemd` user or system service** that **restarts on failure**, starts **after the network is online** (so DNS for `peter.toomanyprojects.dev` resolves), and logs to **journald**.

**Assumption:** Stage 3 complete—TLS works when launched manually.

**Do not implement:** Pete firmware.

---

## 2. Prerequisites

- [ ] Stage 3 HTTPS verified via `curl` from another host.
- [ ] Known **venv path** or **uv** environment path on the Pi for `uvicorn` executable.
- [ ] TLS cert/key paths stable (e.g. under `/etc/irpete/`).

---

## 3. Goals

1. **`irpete-peter.service`** (name may vary) runs Uvicorn with SSL env vars.
2. **`Restart=always`** + sensible `RestartSec` (e.g. 3–5s).
3. **`After=network-online.target`** (and typically `Wants=` it) to reduce “API up but DNS broken” races.
4. **EnvironmentFile** pointing to `/etc/irpete/peter.env` (mode `0600`) containing `IRPETE_API_KEY`, TLS paths, bind host/port.
5. **Operator docs:** enable service, start on boot, `journalctl` usage, **cold reboot test** checklist.

---

## 4. Out of scope

- Docker / Kubernetes.
- Automated certificate renewal (unless you already have it—document only).
- logrotate for files (journald only in v1).

---

## 5. Technical design notes (research-backed)

### 5.1 `network-online.target` caveat

`network-online.target` means “some configured waiter decided the network is up,” not always “Wi‑Fi has DHCP.” For Wi‑Fi-only Pis, ensure **`systemd-networkd-wait-online.service`** or **`NetworkManager-wait-online.service`** is enabled, or document that **Ethernet** is preferred for headless reliability.

**Reference:** `man systemd.special` — `network-online.target`

### 5.2 User vs system service

**System service** (`/etc/systemd/system/`) is simplest for binding low ports and reading `/etc/irpete/`. If running as non-root on high port, document `User=` directive.

### 5.3 Hardening (lightweight v1)

- `NoNewPrivileges=yes` (if compatible with your stack)
- `PrivateTmp=yes`
- Avoid logging secrets; ensure Uvicorn does not print env at startup in debug unintentionally.

### 5.4 Working directory

Set `WorkingDirectory=` to the install path of the repo or configured app root so relative SQLite paths (if any) are stable.

---

## 6. Implementation checklist (suggested order)

1. Add `deploy/systemd/irpete-peter.service` **template** in repo (no secrets).
2. Add `deploy/peter.env.example` listing required keys (no values).
3. Document install steps: copy unit to `/etc/systemd/system/`, `daemon-reload`, `enable --now`.
4. Document creating `/etc/irpete/peter.env` with `chmod 600`.
5. Run cold reboot test and capture expected `journalctl` lines in README.

---

## 7. Verification (exit criteria)

- [ ] `systemctl enable --now irpete-peter` brings HTTPS up without manual `cd`.
- [ ] `systemctl status` shows **active (running)** after boot.
- [ ] Power cycle Pi: within **reasonable time** (document), `curl https://peter…/v1/health` succeeds.
- [ ] Intentional crash (`kill -9` uvicorn worker) → service restarts automatically.

---

## 8. Handoff to Stage 5

Pete needs a **stable URL** `https://peter.toomanyprojects.dev:<port>` and **CA PEM** + **API key** embedded in firmware secrets. Confirm:

- Port number is documented in README + [REFERENCE.md](REFERENCE.md) if finalized.
- `journalctl -u irpete-peter -f` is enough for first Pete bring-up debugging.

---

## 9. To-do list (Stage 4 execution — start fresh)

- [ ] Add systemd unit template + `peter.env.example` to repo.
- [ ] Document install/enable commands for Raspberry Pi OS.
- [ ] Configure `After=network-online.target` (+ `Wants=` as needed).
- [ ] Configure `Restart=always` + `RestartSec`.
- [ ] Validate env file permissions and ownership.
- [ ] Perform cold reboot acceptance §7.
- [ ] Update README troubleshooting (DNS not ready, wrong WorkingDirectory, TLS file unreadable).

---

## 10. References

- [systemd.service(5)](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
- [systemd.unit(5)](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html)
