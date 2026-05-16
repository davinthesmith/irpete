"""Tests for capture session files and pid cleanup (no GPIO)."""

from __future__ import annotations

import os
from pathlib import Path

from irpete.capture_state import (
    CandidatePayload,
    cleanup_stale_pidfile,
    is_pid_alive,
    read_candidate,
    read_recorder_pid,
    write_candidate,
    write_recorder_pid,
)


def test_write_read_candidate(tmp_path: Path) -> None:
    sd = tmp_path / "cap"
    c = CandidatePayload(carrier_hz=38000, raw_us=[1000, 500, 1000, 500])
    write_candidate(sd, c)
    got = read_candidate(sd)
    assert got is not None
    assert got.carrier_hz == 38000
    assert got.raw_us == c.raw_us


def test_cleanup_stale_pidfile_removes_dead_pid(tmp_path: Path) -> None:
    sd = tmp_path / "cap"
    sd.mkdir()
    # Max PID on Linux is large; this PID should not exist.
    write_recorder_pid(sd, 999_999_999)
    assert read_recorder_pid(sd) == 999_999_999
    cleanup_stale_pidfile(sd)
    assert read_recorder_pid(sd) is None


def test_is_pid_alive_zero() -> None:
    assert is_pid_alive(0) is False


def test_read_candidate_missing_returns_none(tmp_path: Path) -> None:
    assert read_candidate(tmp_path / "nope") is None


def test_read_candidate_rejects_malformed_json(tmp_path: Path) -> None:
    sd = tmp_path / "cap"
    sd.mkdir()
    (sd / "candidate.json").write_text("{", encoding="utf-8")
    assert read_candidate(sd) is None


def test_read_candidate_accepts_minimal_dict(tmp_path: Path) -> None:
    sd = tmp_path / "cap"
    write_candidate(sd, CandidatePayload(38000, [900, 450, 900, 450]))
    got = read_candidate(sd)
    assert got is not None
    assert got.raw_us[0] == 900


def test_pid_roundtrip(tmp_path: Path) -> None:
    sd = tmp_path / "cap"
    write_recorder_pid(sd, os.getpid())
    assert read_recorder_pid(sd) == os.getpid()
    cleanup_stale_pidfile(sd)
    # Our own PID is alive, so cleanup does NOT remove it by design.
    assert read_recorder_pid(sd) == os.getpid()
