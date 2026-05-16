"""Guardrails for Stage 4 systemd deploy artifacts (``plans/build/stage-04-peter-systemd.md``)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


def _repo_peter() -> Path:
    return Path(__file__).resolve().parents[1]


def test_systemd_unit_has_boot_order_restart_and_env_file() -> None:
    """Exit criteria: network-online ordering, Restart=always, EnvironmentFile for /etc/irpete/peter.env."""
    unit = _repo_peter() / "deploy" / "systemd" / "irpete-peter.service"
    text = unit.read_text(encoding="utf-8")
    assert "After=network-online.target" in text
    assert "Wants=network-online.target" in text
    assert "Restart=always" in text
    m = re.search(r"^RestartSec=(\d+)", text, flags=re.MULTILINE)
    assert m is not None, "RestartSec must be set (Stage 4: sensible delay before restart)"
    assert 1 <= int(m.group(1)) <= 60
    assert "EnvironmentFile=/etc/irpete/peter.env" in text
    assert "Type=simple" in text
    assert "ExecStart=" in text and "irpete.main" in text
    assert "WorkingDirectory=" in text
    assert "NoNewPrivileges=yes" in text
    assert "PrivateTmp=yes" in text
    assert "WantedBy=multi-user.target" in text


def test_deploy_env_example_lists_tls_and_listen_vars() -> None:
    """EnvironmentFile contract: API key, TLS paths, bind host/port for HTTPS prod."""
    example = _repo_peter() / "deploy" / "peter.env.example"
    text = example.read_text(encoding="utf-8")
    for key in (
        "IRPETE_API_KEY",
        "IRPETE_HOST",
        "IRPETE_PORT",
        "IRPETE_TLS_CERTFILE",
        "IRPETE_TLS_KEYFILE",
    ):
        assert key in text, f"deploy/peter.env.example must document {key}"


def test_readme_documents_systemd_operator_flow() -> None:
    """README must cover install, journalctl, cold reboot, crash restart, and troubleshooting."""
    readme = _repo_peter() / "README.md"
    text = readme.read_text(encoding="utf-8")
    for needle in (
        "irpete-peter",
        "network-online.target",
        "journalctl -u irpete-peter",
        "daemon-reload",
        "enable --now",
        "Cold reboot",
        "kill -9",
        "Restart=always",
        "/etc/irpete/peter.env",
        "chmod 600",
        "WorkingDirectory",
        "systemd-networkd-wait-online",
        "NetworkManager-wait-online",
    ):
        assert needle in text, f"README must mention {needle!r} for Stage 4 operators"


@pytest.mark.skipif(not shutil.which("systemd-analyze"), reason="systemd-analyze not installed")
def test_systemd_unit_passes_systemd_analyze_verify() -> None:
    """When systemd tooling exists (e.g. Linux CI or Pi), the unit must be syntactically valid."""
    unit = _repo_peter() / "deploy" / "systemd" / "irpete-peter.service"
    proc = subprocess.run(
        ["systemd-analyze", "verify", str(unit)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
