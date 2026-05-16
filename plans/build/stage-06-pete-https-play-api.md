# Stage 6 — Pete: HTTPS server + `/v1/play` + busy guard + end-to-end curl

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are extending Stage 5 firmware so Pete exposes **HTTPS** (BearSSL server) and implements **`POST /v1/play`** per [REFERENCE.md §5](REFERENCE.md):

- Client presents **Bearer** token (same `IRPETE_API_KEY` model or a **dedicated Pete key**—v1 uses **one shared key** unless you update REFERENCE).
- Body JSON includes **`label`**.
- Pete **fetches** envelope from Peter (TLS client, already proven in Stage 5), then **IR send**.
- If a play is already running, return **409 Conflict** (simple global `busy` flag).

**Assumption:** Stage 5 **fetch + IR** path works reliably.

**Out of scope:** OTA, driver registry refactor (Stage 7), Home Assistant.

---

## 2. Prerequisites

- [ ] Stage 5 verified on bench.
- [ ] **Server certificate** for Pete available (wildcard `*.toomanyprojects.dev` SAN includes device hostname **or** use IP cert—prefer hostname clients will use).
- [ ] Laptop trusts Pete server cert **or** curl uses `--cacert` pointing at same chain used by Pete server material.

---

## 3. Goals

1. **BearSSL-enabled HTTPS listener** on Pete (choose high port if easier, e.g. **8443**, document in README).
2. Parse **`POST /v1/play`** JSON safely (ArduinoJson; reject oversized bodies).
3. Auth: reject missing/wrong Bearer with **401**.
4. Concurrency: **409** if busy.
5. **End-to-end demo:** `curl` from laptop → Pete → Peter → IR.

---

## 4. Technical design notes (research-backed)

### 4.1 ESP8266 HTTPS server patterns

The ESP8266 Arduino core provides **`BearSSL::WiFiServerSecure`** / secure server APIs (exact class names vary by core version—verify against your installed **ESP8266 Arduino core** version).

**Constraints:**

- Keep **request bodies small** (only `label` + maybe a few flags).
- Prefer **synchronous** handling in the HTTP callback path: **parse → fetch → send → respond**, all while marking `busy=true`, then `busy=false` in a `finally`-style pattern (RAII or explicit).

### 4.2 URL path and method

Recommend:

- `POST /v1/play`
- JSON: `{"label":"tv_power"}`

Alternative query param is harder for JSON clients—prefer JSON body.

### 4.3 TLS material for Pete server

Options:

1. **Same wildcard cert** as internal domain (if your CA allows installing on device—operationally odd but possible as PEM in flash).
2. **Dedicated leaf** `pete.toomanyprojects.dev` stored in secrets.

Document `curl` with **`--resolve`** if DNS for `pete.toomanyprojects.dev` is not globally propagated but you want SNI testing:

```bash
curl -v --cacert pete-chain.pem \
  --resolve pete.toomanyprojects.dev:8443:192.168.1.50 \
  -H "Authorization: Bearer $IRPETE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label":"tv_power"}' \
  https://pete.toomanyprojects.dev:8443/v1/play
```

### 4.4 Error mapping

| Condition | HTTP |
|-----------|------|
| Missing/wrong Bearer | 401 |
| Unknown label (from Peter 404) | 404 or 502—**pick and document** (404 passthrough vs gateway 502) |
| Peter TLS/connect failure | 503 |
| Busy | 409 |
| Success | 200 (body optional JSON `{"ok":true}`) |

---

## 5. Implementation checklist (suggested order)

1. Add server cert + key PEMs to secrets template (gitignored).
2. Initialize secure server socket bound to port.
3. Implement minimal HTTP parser OR use a lightweight ESP8266 web server library **only if** it supports BearSSL server cleanly—evaluate memory tradeoffs; **minimal manual parser** is acceptable for single-route v1.
4. Wire `POST /v1/play` only (reject other paths with 404).
5. Reuse Stage 5 client function `playLabel(const char* label)` internally.
6. Add `busy` mutex flag (no FreeRTOS complexity required; disable interrupts only if absolutely necessary—prefer atomic bool).
7. Extend README with curl recipes and troubleshooting TLS hostname mismatches.

---

## 6. Verification (exit criteria)

- [ ] `curl` HTTPS to Pete succeeds with valid auth and label.
- [ ] Wrong Bearer → **401**.
- [ ] Two overlapping curls: second returns **409** (or times out only if first holds too long—document max duration).
- [ ] IR observed on each successful play.
- [ ] Serial logs show distinct phases: **HTTP in → TLS out → IR → HTTP out**.

---

## 7. Handoff to Stage 7

Stage 7 refactors IR sending behind a **driver interface** without changing externally visible HTTP behavior. Freeze:

- URL path `/v1/play`
- JSON body shape
- Status codes

---

## 8. To-do list (Stage 6 execution — start fresh)

- [ ] Add Pete server TLS cert/key to secrets template.
- [ ] Implement HTTPS listener on chosen port.
- [ ] Implement `POST /v1/play` parsing + validation.
- [ ] Enforce Bearer auth.
- [ ] Integrate Stage 5 Peter fetch + IR send with busy guard.
- [ ] Map Peter/client errors to stable HTTP codes (document).
- [ ] Update README with curl examples (DNS, `--resolve`, cacert).
- [ ] Run end-to-end verification §6.

---

## 9. References

- ESP8266 Arduino core BearSSL server examples (search core docs for `WiFiServerSecure` / `BearSSLServer`)
- [curl TLS debugging](https://everything.curl.dev/ssl/ciphers.html)
