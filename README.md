# IRPete

IR capture and replay stack: **Peter** (Raspberry Pi HTTPS API + SQLite) and **Pete** (ESP8266 HTTPS client/server + IR). Authoritative contracts live in [`plans/build/REFERENCE.md`](plans/build/REFERENCE.md).

- **Peter (Python):** [`peter/README.md`](peter/README.md)
- **Pete (firmware):** [`firmware/pete/README.md`](firmware/pete/README.md)

## Pete hardware-in-the-loop (HIL) checklist

Operator runs on a bench with Peter up and Pete on Wi‑Fi:

1. **NEC-like remote** (common TV): capture on Peter (Stage 2), play via Pete; device responds.
2. **Long RAW / toggle-style remote:** ensure envelope length near your configured max still plays (validates RAM sizing).
3. **Rapid repeat:** fire same label **10×** sequentially; no heap corruption / resets (watch Serial).
4. **Auth negative:** remove Bearer temporarily in curl; expect **401**.
5. **Busy negative:** trigger overlapping requests; expect **409** on second.
6. **Power cycle Pete:** first play after reboot succeeds without manual Peter restart.

Details, pinout, IR transistor circuit, and curl examples: [`firmware/pete/README.md`](firmware/pete/README.md).
