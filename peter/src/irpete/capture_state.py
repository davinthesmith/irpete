"""Cross-process capture session: recorder PID file + candidate JSON on disk."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from irpete.capture_paths import CANDIDATE_JSON, RECORDER_PID_FILE


def _pid_path(state_dir: Path) -> Path:
    return state_dir / RECORDER_PID_FILE


def _candidate_path(state_dir: Path) -> Path:
    return state_dir / CANDIDATE_JSON


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_recorder_pid(state_dir: Path) -> int | None:
    p = _pid_path(state_dir)
    if not p.is_file():
        return None
    try:
        line = p.read_text(encoding="utf-8").strip()
        return int(line)
    except (OSError, ValueError):
        return None


def write_recorder_pid(state_dir: Path, pid: int) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    _pid_path(state_dir).write_text(str(pid) + "\n", encoding="utf-8")


def clear_recorder_pid(state_dir: Path) -> None:
    try:
        _pid_path(state_dir).unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_stale_pidfile(state_dir: Path) -> None:
    pid = read_recorder_pid(state_dir)
    if pid is None:
        return
    if not is_pid_alive(pid):
        clear_recorder_pid(state_dir)


@dataclass(frozen=True)
class CandidatePayload:
    """In-RAM capture result written by the recorder process."""

    carrier_hz: int
    raw_us: list[int]


def write_candidate(state_dir: Path, payload: CandidatePayload) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    data = {"carrier_hz": payload.carrier_hz, "raw_us": payload.raw_us}
    _candidate_path(state_dir).write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def read_candidate(state_dir: Path) -> CandidatePayload | None:
    p = _candidate_path(state_dir)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        carrier = int(raw["carrier_hz"])
        ru = raw["raw_us"]
        if not isinstance(ru, list):
            return None
        timing = [int(x) for x in ru]
    except (KeyError, TypeError, ValueError):
        return None
    return CandidatePayload(carrier_hz=carrier, raw_us=timing)


def spawn_recorder_subprocess(
    state_dir: Path, pin: int, carrier_hz: int, gpiochip: int
) -> int:
    """Start ``python -m irpete.capture_worker``; return child PID."""
    cmd = [
        sys.executable,
        "-m",
        "irpete.capture_worker",
        str(state_dir),
        str(pin),
        str(carrier_hz),
        str(gpiochip),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL)
    return int(proc.pid)


def stop_recorder(
    state_dir: Path, *, wait_timeout_s: float = 30.0, poll_interval_s: float = 0.05
) -> None:
    """SIGTERM the recorder PID from ``state_dir`` and wait for exit."""
    pid = read_recorder_pid(state_dir)
    if pid is None:
        raise RuntimeError("No active capture session (missing recorder.pid).")
    if not is_pid_alive(pid):
        clear_recorder_pid(state_dir)
        raise RuntimeError(
            f"Recorder PID {pid} is not running (stale pid file cleaned up)."
        )
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        clear_recorder_pid(state_dir)
        raise RuntimeError(f"Recorder PID {pid} exited before SIGTERM.") from None

    deadline = time.monotonic() + wait_timeout_s
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            clear_recorder_pid(state_dir)
            return
        time.sleep(poll_interval_s)

    raise TimeoutError(
        f"Recorder PID {pid} did not exit within {wait_timeout_s:.1f}s after SIGTERM."
    )
