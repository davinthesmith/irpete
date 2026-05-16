"""CLI tests: validate / preview / commit with mocked candidate files (no GPIO).

Maps to ``plans/build/stage-02-manual-capture-cli.md`` §7 where automatable:
``commit`` + Stage 1 ``GET``, invalid/empty capture fails validation, preview summary.
Pi-only ``start``/``stop``/real remote remains manual or ``@pytest.mark.hardware``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from irpete.capture_state import CandidatePayload, write_candidate
from irpete.gpio_timing import _ts_delta_to_us
from irpete.repository import connect, get_by_label, init_db

runner = CliRunner()


def _write_good_candidate(state_dir: Path) -> None:
    write_candidate(
        state_dir,
        CandidatePayload(carrier_hz=38000, raw_us=[1000, 500, 1000, 500]),
    )


def test_ts_delta_to_us() -> None:
    assert _ts_delta_to_us(5_000_000) == 5000  # ns → µs
    assert _ts_delta_to_us(500_000) == 500
    assert _ts_delta_to_us(0) == 1


def test_validate_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sd = tmp_path / "state"
    _write_good_candidate(sd)
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(app, ["validate", "--state-dir", str(sd)])
    assert r.exit_code == 0
    assert "OK" in r.stdout


def test_validate_rejects_short_raw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sd = tmp_path / "state"
    write_candidate(sd, CandidatePayload(38000, [1000]))
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(app, ["validate", "--state-dir", str(sd)])
    assert r.exit_code == 1
    assert "Validation failed" in r.stdout or "Validation failed" in r.stderr


def test_validate_rejects_empty_raw_us(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stage 2 §7: invalid capture (e.g. empty) fails validate with an actionable message."""
    sd = tmp_path / "state"
    write_candidate(sd, CandidatePayload(38000, []))
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(app, ["validate", "--state-dir", str(sd)])
    assert r.exit_code == 1
    out = r.stdout + r.stderr
    assert "Validation failed" in out


def test_commit_rejects_empty_raw_us(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``commit`` runs the same validation gate as ``validate`` before any SQLite write."""
    sd = tmp_path / "state"
    db = tmp_path / "db.sqlite"
    write_candidate(sd, CandidatePayload(38000, []))
    monkeypatch.setenv("IRPETE_DB_PATH", str(db))
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(
        app,
        ["commit", "--label", "bad", "--state-dir", str(sd)],
    )
    assert r.exit_code == 1
    conn = connect(db)
    try:
        init_db(conn)
        assert get_by_label(conn, "bad") is None
    finally:
        conn.close()


def test_preview_shows_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sd = tmp_path / "state"
    _write_good_candidate(sd)
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(app, ["preview", "--state-dir", str(sd), "--head", "2", "--tail", "2"])
    assert r.exit_code == 0
    assert "pulse_segments: 4" in r.stdout
    assert "total_duration_us: 3000" in r.stdout


def test_commit_persists_to_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sd = tmp_path / "state"
    db = tmp_path / "db.sqlite"
    _write_good_candidate(sd)
    monkeypatch.setenv("IRPETE_DB_PATH", str(db))
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(
        app,
        ["commit", "--label", "cli_btn", "--state-dir", str(sd)],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "Committed" in r.stdout

    conn = connect(db)
    try:
        init_db(conn)
        row = get_by_label(conn, "cli_btn")
        assert row is not None
        assert row["label"] == "cli_btn"
        assert row["carrier_hz"] == 38000
        assert row["raw_us"] == [1000, 500, 1000, 500]
    finally:
        conn.close()


def test_commit_visible_via_stage1_http_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 2 §7: envelope committed via CLI round-trips through ``GET /v1/signals/{label}``."""
    sd = tmp_path / "state"
    db = tmp_path / "db.sqlite"
    api_key = "integration-test-key"
    _write_good_candidate(sd)
    monkeypatch.setenv("IRPETE_DB_PATH", str(db))
    monkeypatch.chdir(tmp_path)

    from irpete.app import create_app
    from irpete.capture_cli import app as cli_app
    from irpete.config import Settings
    from starlette.testclient import TestClient

    r = runner.invoke(
        cli_app,
        ["commit", "--label", "test_btn", "--state-dir", str(sd)],
    )
    assert r.exit_code == 0, r.stdout + r.stderr

    settings = Settings(
        api_key=api_key,
        db_path=db,
        host="127.0.0.1",
        port=8000,
    )
    with TestClient(create_app(settings)) as client:
        got = client.get(
            "/v1/signals/test_btn",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert got.status_code == 200
        body = got.json()
        assert body["label"] == "test_btn"
        assert body["raw_us"] == [1000, 500, 1000, 500]


def test_validate_missing_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sd = tmp_path / "empty_state"
    sd.mkdir()
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(app, ["validate", "--state-dir", str(sd)])
    assert r.exit_code == 1


def test_stop_without_active_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sd = tmp_path / "empty_state"
    sd.mkdir()
    monkeypatch.chdir(tmp_path)
    from irpete.capture_cli import app

    r = runner.invoke(app, ["stop", "--state-dir", str(sd)])
    assert r.exit_code == 1


@pytest.mark.hardware
def test_hardware_placeholder_skipped() -> None:
    pytest.skip("Manual / Pi-only: wire TSOP to BCM 18, run start → stop → validate.")
