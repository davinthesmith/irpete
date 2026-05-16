"""Typer CLI: manual TSOP capture (RAM via recorder process → validate → commit)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from irpete.capture_paths import default_state_dir
from irpete.capture_state import (
    CandidatePayload,
    cleanup_stale_pidfile,
    is_pid_alive,
    read_candidate,
    read_recorder_pid,
    spawn_recorder_subprocess,
    stop_recorder,
    write_recorder_pid,
)
from irpete.config import resolve_db_path
from irpete.repository import connect, init_db, upsert_signal
from irpete.validate import SCHEMA_VERSION_V1, validate_envelope

app = typer.Typer(
    name="irpete-capture",
    help="Record TSOP pulse timings on a Raspberry Pi, validate, then commit to SQLite.",
    no_args_is_help=True,
)


def _resolve_state_dir(state_dir: Optional[Path]) -> Path:
    return state_dir if state_dir is not None else default_state_dir()


_STATE_HELP = (
    "Directory for recorder.pid and candidate.json "
    "(default: XDG_STATE_HOME/irpete/capture or ~/.local/state/irpete/capture)."
)


@app.command()
def start(
    state_dir: Optional[Path] = typer.Option(None, "--state-dir", help=_STATE_HELP),
    pin: int = typer.Option(18, "--pin", help="BCM GPIO for TSOP output (default 18 per REFERENCE)."),
    carrier_hz: int = typer.Option(
        38000,
        "--carrier-hz",
        help="Stored carrier frequency (TSOP does not measure carrier).",
    ),
    gpiochip: int = typer.Option(
        0,
        "--gpio-chip",
        help="lgpio gpiochip index (Pi 5 often 4; Pi 4 typically 0).",
    ),
) -> None:
    """Begin recording edges into RAM (background process); use ``stop`` to finalize."""
    sd = _resolve_state_dir(state_dir)
    cleanup_stale_pidfile(sd)
    existing = read_recorder_pid(sd)
    if existing is not None and is_pid_alive(existing):
        typer.echo(
            f"A capture session is already active (PID {existing}). Stop it first.",
            err=True,
        )
        raise typer.Exit(code=1)

    pid = spawn_recorder_subprocess(sd, pin, carrier_hz, gpiochip)
    write_recorder_pid(sd, pid)
    time.sleep(0.15)
    if not is_pid_alive(pid):
        cleanup_stale_pidfile(sd)
        typer.echo(
            "Recorder exited immediately. Is `lgpio` installed and GPIO accessible? "
            "See README (Training workflow).",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(
        f"Recording… PID {pid} on BCM GPIO {pin}, carrier_hz={carrier_hz}, gpiochip={gpiochip}. "
        f"State dir: {sd}. Ctrl+C in this shell does not stop the recorder; run: irpete-capture stop"
    )


@app.command()
def stop(
    state_dir: Optional[Path] = typer.Option(None, "--state-dir", help=_STATE_HELP),
) -> None:
    """Stop recording and write ``candidate.json`` (still no SQLite write)."""
    sd = _resolve_state_dir(state_dir)
    try:
        stop_recorder(sd)
    except (RuntimeError, TimeoutError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from e

    cand = read_candidate(sd)
    if cand is None:
        typer.echo("Recording stopped but candidate.json was not written.", err=True)
        raise typer.Exit(code=1)
    typer.echo(
        f"Stopped. Candidate ready: {len(cand.raw_us)} pulse row(s), carrier_hz={cand.carrier_hz}."
    )


def _require_candidate(sd: Path) -> CandidatePayload:
    cand = read_candidate(sd)
    if cand is None:
        typer.echo(
            "No candidate capture found. Run `start`, press your remote, then `stop`.",
            err=True,
        )
        raise typer.Exit(code=1)
    return cand


@app.command()
def validate(
    state_dir: Optional[Path] = typer.Option(None, "--state-dir", help=_STATE_HELP),
    label: str = typer.Option(
        "capture_preview",
        "--label",
        help="Label used only for validation (commit uses its own --label).",
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        help="Optional notes field for validation preview.",
    ),
) -> None:
    """Run the same envelope checks as ``POST /v1/signals`` (normalization on)."""
    sd = _resolve_state_dir(state_dir)
    cand = _require_candidate(sd)
    body: dict = {
        "schema_version": SCHEMA_VERSION_V1,
        "label": label,
        "carrier_hz": cand.carrier_hz,
        "raw_us": cand.raw_us,
    }
    if notes is not None:
        body["notes"] = notes
    try:
        validate_envelope(body, normalize=True)
    except ValidationError as e:
        typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(code=1) from e
    except ValueError as e:
        typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo("OK — envelope passes validation rules (normalized).")


@app.command()
def preview(
    state_dir: Optional[Path] = typer.Option(None, "--state-dir", help=_STATE_HELP),
    head: int = typer.Option(6, "--head", min=0),
    tail: int = typer.Option(6, "--tail", min=0),
) -> None:
    """Print a short human summary of the last candidate (no schema validation)."""
    sd = _resolve_state_dir(state_dir)
    cand = _require_candidate(sd)
    n = len(cand.raw_us)
    total = sum(cand.raw_us)
    typer.echo(f"carrier_hz: {cand.carrier_hz}")
    typer.echo(f"pulse_segments: {n}")
    typer.echo(f"total_duration_us: {total}")
    if n == 0:
        return
    if head + tail >= n:
        typer.echo(f"raw_us: {cand.raw_us}")
        return
    typer.echo(f"raw_us[:{head}]: {cand.raw_us[:head]}")
    typer.echo(f"raw_us[-{tail}:]: {cand.raw_us[-tail:]}")


@app.command()
def commit(
    label: str = typer.Option(..., "--label", help="Upsert key / envelope label."),
    state_dir: Optional[Path] = typer.Option(None, "--state-dir", help=_STATE_HELP),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        help="Optional human notes stored in the envelope.",
    ),
    repeat: Optional[int] = typer.Option(
        None,
        "--repeat",
        help="Optional repeat count (reserved field).",
    ),
) -> None:
    """Validate like HTTP POST, then persist to SQLite (same upsert rules as the API)."""
    sd = _resolve_state_dir(state_dir)
    cand = _require_candidate(sd)
    body: dict = {
        "schema_version": SCHEMA_VERSION_V1,
        "label": label,
        "carrier_hz": cand.carrier_hz,
        "raw_us": cand.raw_us,
    }
    if notes is not None:
        body["notes"] = notes
    if repeat is not None:
        body["repeat"] = repeat
    try:
        env = validate_envelope(body, normalize=True)
    except ValidationError as e:
        typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(code=1) from e
    except ValueError as e:
        typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(code=1) from e

    db_path = resolve_db_path()
    conn = connect(db_path)
    try:
        init_db(conn)
        upsert_signal(conn, env)
        conn.commit()
    finally:
        conn.close()

    typer.echo(f"Committed label={label!r} to {db_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
