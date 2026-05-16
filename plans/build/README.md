# IRPete — build plans (per-stage execution)

This directory holds **verbose, self-contained execution plans** for each **sequential** implementation stage of IRPete. Each stage is intended to run in a **new chat or agent session** after the previous stage’s exit criteria are satisfied.

## How to use these documents in a fresh session

1. Open **[REFERENCE.md](REFERENCE.md)** first. It is the **single shared contract** (names, paths, API shapes, TLS/auth rules, hardware defaults). Individual stage plans **must not redefine** those contracts silently—if something must change, update **REFERENCE.md** and then adjust the affected stage plans.
2. Open **only the stage plan you are executing** (e.g. `stage-03-…md`). Treat its **To-do list** as the working checklist for that session.
3. When the stage’s **Verification** and **Handoff** sections are complete, stop. A **new** session should start the next stage.

## Stage index (execute in order)

| Order | Document | Summary |
|------:|----------|---------|
| 1 | [stage-01-peter-contract-and-core.md](stage-01-peter-contract-and-core.md) | JSON envelope + SQLite + FastAPI CRUD + Bearer + pytest (HTTP TestClient OK). |
| 2 | [stage-02-manual-capture-cli.md](stage-02-manual-capture-cli.md) | Typer CLI: manual record → RAM → validate → commit; TSOP GPIO 18. |
| 3 | [stage-03-peter-https-dns.md](stage-03-peter-https-dns.md) | Uvicorn TLS for `peter.toomanyprojects.dev`; CA material for Pete. |
| 4 | [stage-04-peter-systemd.md](stage-04-peter-systemd.md) | systemd: `Restart=always`, `network-online`, install docs, cold-boot test. |
| 5 | [stage-05-pete-tls-client-ir.md](stage-05-pete-tls-client-ir.md) | PlatformIO: Wi‑Fi + HTTPS GET Peter + `sendRaw` (no Pete HTTPS API yet). |
| 6 | [stage-06-pete-https-play-api.md](stage-06-pete-https-play-api.md) | Pete HTTPS server + `/v1/play` + 409 busy + E2E curl. |
| 7 | [stage-07-hardware-abstraction-docs.md](stage-07-hardware-abstraction-docs.md) | Driver registry + `IrLedDriver` + operator README / HIL checklist. |
| 8 | [stage-08-ci-release-hygiene.md](stage-08-ci-release-hygiene.md) | GitHub Actions (or equivalent): pytest + `pio run`. |

## Related material

- Deferred features: [../later.md](../later.md)
- High-level architecture narrative (may live outside this repo in Cursor’s plan store): search for plan name **IRPete architecture plan** — the **authoritative operational contract for implementers is [REFERENCE.md](REFERENCE.md)**.
