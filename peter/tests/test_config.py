"""Settings / environment contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from irpete.config import load_settings


def test_load_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IRPETE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="IRPETE_API_KEY"):
        load_settings()


def test_load_settings_uses_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = tmp_path / "e.db"
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.setenv("IRPETE_DB_PATH", str(db))
    monkeypatch.setenv("IRPETE_HOST", "0.0.0.0")
    monkeypatch.setenv("IRPETE_PORT", "9000")
    s = load_settings()
    assert s.api_key == "k"
    assert s.db_path == db
    assert s.host == "0.0.0.0"
    assert s.port == 9000


def test_load_settings_default_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.delenv("IRPETE_PORT", raising=False)
    s = load_settings()
    assert s.port == 8000


def test_load_settings_rejects_bad_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.setenv("IRPETE_PORT", "nope")
    with pytest.raises(RuntimeError, match="IRPETE_PORT"):
        load_settings()


def test_resolve_db_path_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``commit`` and the API must agree on the same file when ``IRPETE_DB_PATH`` is set."""
    from irpete.config import resolve_db_path

    p = tmp_path / "shared.db"
    monkeypatch.setenv("IRPETE_DB_PATH", str(p))
    assert resolve_db_path() == p


def test_resolve_db_path_default_under_peter_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from irpete.config import resolve_db_path

    monkeypatch.delenv("IRPETE_DB_PATH", raising=False)
    p = resolve_db_path()
    assert p.name == "irpete.db"
    assert p.parent.name == "data"


def test_load_settings_tls_requires_both(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.setenv("IRPETE_TLS_CERTFILE", "/tmp/a.pem")
    monkeypatch.delenv("IRPETE_TLS_KEYFILE", raising=False)
    with pytest.raises(RuntimeError, match="both"):
        load_settings()


def test_load_settings_tls_missing_cert_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = tmp_path / "k.pem"
    key.write_text("x")
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.setenv("IRPETE_TLS_CERTFILE", str(tmp_path / "missing.pem"))
    monkeypatch.setenv("IRPETE_TLS_KEYFILE", str(key))
    with pytest.raises(RuntimeError, match="IRPETE_TLS_CERTFILE"):
        load_settings()


def test_load_settings_tls_missing_key_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cert = tmp_path / "c.pem"
    cert.write_text("x")
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.setenv("IRPETE_TLS_CERTFILE", str(cert))
    monkeypatch.setenv("IRPETE_TLS_KEYFILE", str(tmp_path / "missing.pem"))
    with pytest.raises(RuntimeError, match="IRPETE_TLS_KEYFILE"):
        load_settings()


def test_load_settings_disable_openapi_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.setenv("IRPETE_DISABLE_OPENAPI", "1")
    assert load_settings().disable_openapi is True


def test_load_settings_tls_paths_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_text("cert")
    key.write_text("key")
    monkeypatch.setenv("IRPETE_API_KEY", "k")
    monkeypatch.setenv("IRPETE_TLS_CERTFILE", str(cert))
    monkeypatch.setenv("IRPETE_TLS_KEYFILE", str(key))
    s = load_settings()
    assert s.tls_certfile == cert
    assert s.tls_keyfile == key
