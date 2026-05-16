"""CI workflow must exist and match jobs documented under ``plans/build/``."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_github_workflow_ci_yml_covers_python_pytest_and_firmware_pio() -> None:
    wf = _repo_root() / ".github" / "workflows" / "ci.yml"
    assert wf.is_file(), "Expected .github/workflows/ci.yml"
    text = wf.read_text(encoding="utf-8")
    assert "pytest" in text
    assert "pio run" in text and "d1_mini" in text
    assert "IRPETE_API_KEY" in text
    assert "working-directory: catalog" in text
    assert "working-directory: firmware/emitter" in text
