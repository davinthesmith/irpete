# Stage 7 — Pete: hardware driver registry + operator docs + HIL checklist

**Common reference (read first):** [REFERENCE.md](REFERENCE.md)

**Build index:** [README.md](README.md)

---

## 1. Execution context (fresh session)

You are **refactoring** Stage 5–6 firmware so IR output flows through a **small driver registry** (extensibility pattern) and expanding **operator documentation**: pinout, **transistor-driven IR LED**, hardware-in-the-loop (HIL) checklist, optional DNS notes for `pete.toomanyprojects.dev`.

**Assumption:** Stage 6 end-to-end **`/v1/play`** works; behavior must remain **functionally identical** after refactor (same HTTP codes and timing ordering).

**Out of scope:** Second physical driver beyond IR (only register a **stub** optional), OTA, new REST endpoints.

---

## 2. Prerequisites

- [ ] Stage 6 complete and stable enough to replay same label repeatedly.

---

## 3. Goals

1. Introduce **`HardwareDriver` interface** (C++ pure virtual or function-table style—match project style) with methods like `const char* id() const` and `bool play(const JsonObject& envelope)`.
2. Register **`IrLedDriver`** as `id = "ir"` (or similar) mapping envelope → `IRsend.sendRaw`.
3. Route `/v1/play` to registry: v1 always selects IR driver; leave hook for future `"kind"` field in JSON.
4. README sections:
   - **Pinout table** (D2 default).
   - **IR circuit** with NPN transistor + base resistor + IR LED current limiting math template.
   - **HIL checklist** (below).
5. Optional: mention **`pete.toomanyprojects.dev`** as doc-only convenience ([REFERENCE.md §3](REFERENCE.md)).

---

## 4. HIL checklist (copy into root `README.md`)

Operator runs on a bench with Peter up and Pete on Wi‑Fi:

1. **NEC-like remote** (common TV): capture on Peter (Stage 2), play via Pete; device responds.
2. **Long RAW / toggle-style remote**: ensure envelope length near your configured max still plays (validates RAM sizing).
3. **Rapid repeat:** fire same label **10×** sequentially; no heap corruption / resets (watch Serial).
4. **Auth negative:** remove Bearer temporarily in curl; expect 401.
5. **Busy negative:** trigger overlapping requests; expect 409 on second.
6. **Power cycle Pete:** first play after reboot succeeds without manual Peter restart.

---

## 5. Technical design notes

### 5.1 Registry shape (minimal)

- `bool registerDriver(std::unique_ptr<HardwareDriver> d);`
- `HardwareDriver* getDriver(const char* id);`
- At boot: `registerDriver(std::make_unique<IrLedDriver>(irsend));`

### 5.2 JSON “kind” field (optional v1)

If added, default **`"kind":"ir"`** when omitted for backward compatibility with earlier Stage 6 clients.

### 5.3 Documentation tone

Write for **future-you** six months later: exact parts, example transistor part numbers (2N2222 or 2N3904 common), and “what good looks like” on a phone camera viewing the IR LED.

---

## 6. Verification (exit criteria)

- [ ] `pio run` still succeeds; firmware size change noted (should not explode).
- [ ] All Stage 6 curl tests still pass unchanged.
- [ ] README contains HIL checklist and wiring diagram (ASCII art acceptable).
- [ ] Code review readability: HTTP layer does not embed IR math.

---

## 7. Handoff to Stage 8

CI should compile firmware and run Peter pytest without changes to **API contract**. If driver refactor moved files, update CI paths accordingly in Stage 8.

---

## 8. To-do list (Stage 7 execution — start fresh)

- [ ] Define `HardwareDriver` interface + registry module.
- [ ] Move IR send code into `IrLedDriver`.
- [ ] Wire `/v1/play` to registry (IR only).
- [ ] Add optional JSON `kind` with default `ir`.
- [ ] Expand README: pinout, transistor IR circuit, safety (don’t stare into IR LED).
- [ ] Add HIL checklist to README.
- [ ] Re-run Stage 6 curl + HIL items §4.

---

## 9. References

- [IRremoteESP8266 sending](https://github.com/crankyoldgit/IRremoteESP8266/wiki#sending-ir-codes)
- General NPN switching for LEDs (electronics tutorials)
