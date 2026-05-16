# Stage 3 — Peter: HTTPS (Uvicorn TLS) + internal DNS + trust bundle for Pete

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are enabling **production-style TLS** for Peter at **`https://peter.toomanyprojects.dev`**, using your **`*.toomanyprojects.dev`** certificate material. The FastAPI **application code** from Stage 1 should remain largely unchanged; TLS is a **deployment concern** (Uvicorn SSL context / CLI flags / env vars).

**Assumption:** Stages **1–2** complete: API + DB + capture work over HTTP in dev; real signals exist in DB for later Pete tests.

**Do not implement:** systemd (Stage 4), Pete firmware (Stage 5) except **documenting** which **CA PEM** to embed in Pete.

---

## 2. Prerequisites

- [ ] DNS A/AAAA (or split-horizon DNS) for `peter.toomanyprojects.dev` → Pi LAN IP.
- [ ] Certificate files on the Pi (wildcard or dedicated): **fullchain PEM** + **private key PEM** paths known.
- [ ] Laptop on same LAN can `ping` the Pi by IP and resolve the hostname.

---

## 3. Goals

1. Run Uvicorn with **`ssl_certfile` + `ssl_keyfile`** (or equivalent SSL context) per [REFERENCE.md §3 and §9](REFERENCE.md).
2. Enforce **HTTPS-only** for “real” operator use; document optional local `127.0.0.1` HTTP dev mode **only** if you keep it, clearly labeled **not for production**.
3. Document **`curl`** verification from a second machine with **full certificate validation** (not `-k`).
4. Produce **operator instructions** for exporting **`ca.pem`** (issuing CA or chain) that Stage 5 will embed in Pete as `setTrustAnchors` / equivalent.

---

## 4. Out of scope

- systemd service hardening (Stage 4).
- ACME automation (optional future; you may issue certs out-of-band).
- Pete firmware.

---

## 5. Technical design notes (research-backed)

### 5.1 Uvicorn SSL parameters

Uvicorn supports:

```bash
uvicorn irpete.main:app --host 0.0.0.0 --port 8443 \
  --ssl-certfile /etc/irpete/fullchain.pem \
  --ssl-keyfile /etc/irpete/privkey.pem
```

Or pass paths via env vars `IRPETE_TLS_CERTFILE` / `IRPETE_TLS_KEYFILE` read by a small launcher script.

**Reference:** [Uvicorn settings — SSL](https://www.uvicorn.org/settings/#ssl)

### 5.2 Port choice

- **8443** avoids needing `CAP_NET_BIND_SERVICE` for binding **443**.
- If you require **443**, use `setcap` on the venv’s `uvicorn` binary or run behind **nginx** (adds complexity—defer nginx unless needed).

Document the chosen port in [REFERENCE.md](REFERENCE.md) changelog if you standardize globally.

### 5.3 Certificate chain trust for Pete

ESP8266 **BearSSL** typically needs:

- Either **issuer CA** as trust anchor (wildcard friendly), or
- A **minimal chain** PEM concatenation that includes what BearSSL can parse.

**Deliverable:** a short **“Export for Pete”** section:

1. Identify which PEM file from your PKI is the **issuer** trusted by clients.
2. Store as `certs/peter-ca.pem` (example only; not committed if private) for operator laptops; Pete embeds **bytes in `secrets.h`** or loads from SPIFFS later (SPIFFS deferred—Stage 5 uses `secrets.h`).

### 5.4 Hostname / SNI

Ensure cert SAN includes **`peter.toomanyprojects.dev`**. Wildcard `*.toomanyprojects.dev` covers it.

### 5.5 Redirect HTTP → HTTPS (optional)

If you accidentally expose plain HTTP on a port, consider **not binding HTTP at all** in v1 (simplest).

---

## 6. Implementation checklist (suggested order)

1. Add env vars to `.env.example`: `IRPETE_TLS_CERTFILE`, `IRPETE_TLS_KEYFILE`, optional `IRPETE_PORT`.
2. Add `scripts/run-peter-https.sh` (optional) that exports env and runs uvicorn with SSL.
3. Update `README.md`: DNS prerequisites, file permissions (`chmod 600` key), `curl` examples.
4. Verify FastAPI docs (`/docs`) over HTTPS (note: Swagger UI may need extra config for self-signed—acceptable to disable `/docs` in prod if awkward).
5. Document **CA export for Pete** with exact `openssl` commands, e.g. extracting issuer or copying known CA file from your PKI.

---

## 7. Verification (exit criteria)

- [ ] `curl -v https://peter.toomanyprojects.dev:<port>/v1/health` succeeds with **valid TLS** (no `-k`).
- [ ] Same with `Authorization: Bearer …` header as required.
- [ ] Wrong/missing Bearer still rejected.
- [ ] README includes **exact** file paths / env var names and troubleshooting (clock skew, wrong SAN, chain incomplete).

---

## 8. Handoff to Stage 4

Stage 4 will run the **same** Uvicorn command under **systemd**. Ensure:

- Logging goes to stdout/stderr (journald friendly).
- No interactive prompts on boot.

---

## 9. To-do list (Stage 3 execution — start fresh)

- [ ] Choose bind port (8443 recommended) and document.
- [ ] Wire TLS file paths into launcher (env-driven).
- [ ] Run HTTPS Uvicorn on Pi; confirm LAN `curl` with verify.
- [ ] Update README: DNS, certs, permissions, curl examples.
- [ ] Write “CA for Pete embedding” openssl / file copy instructions.
- [ ] Update [REFERENCE.md](REFERENCE.md) §changelog if port/env names standardized.
- [ ] Optional: disable public `/docs` in production via env flag.

---

## 10. References

- [Uvicorn SSL](https://www.uvicorn.org/settings/#ssl)
- [OpenSSL s_client](https://docs.openssl.org/master/man1/openssl-s_client1/) for debugging chains
