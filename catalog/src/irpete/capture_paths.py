"""Filesystem locations for the manual capture CLI (cross-process state)."""

from __future__ import annotations

import os
from pathlib import Path


def default_state_dir() -> Path:
    """XDG-style state directory for capture session files."""
    base = os.environ.get("XDG_STATE_HOME", "").strip()
    if base:
        return Path(base) / "irpete" / "capture"
    return Path.home() / ".local" / "state" / "irpete" / "capture"


RECORDER_PID_FILE = "recorder.pid"
CANDIDATE_JSON = "candidate.json"
