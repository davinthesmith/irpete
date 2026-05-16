"""Guardrails for Catalog HTTPS/LAN operator docs (see ``plans/build/``)."""

from __future__ import annotations

from pathlib import Path


def test_readme_documents_https_env_and_troubleshooting() -> None:
    """Exit criteria: exact env names + troubleshooting (SAN, clock, chain)."""
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    for needle in (
        "IRPETE_TLS_CERTFILE",
        "IRPETE_TLS_KEYFILE",
        "IRPETE_DISABLE_OPENAPI",
        "8443",
        "SAN",
        "NTP",
        "clock skew",
        "chain",
        "openssl s_client",
        "catalog-ca.pem",
    ):
        assert needle in text, f"README must mention {needle!r} for operator TLS/Emitter handoff"
