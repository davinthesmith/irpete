"""HTTPS smoke tests (OpenSSL-generated certs; threaded Uvicorn)."""

from __future__ import annotations

import socket
import ssl
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn

from irpete.app import create_app
from irpete.config import Settings, load_settings
from irpete.main import uvicorn_kwargs


def _openssl_self_signed_pair(tmp_path: Path) -> tuple[Path, Path]:
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(key),
                "-out",
                str(cert),
                "-days",
                "1",
                "-nodes",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        pytest.skip(f"openssl self-signed generation failed: {e}")
    return cert, key


def _wait_tcp(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"nothing listening on {host}:{port}")


@pytest.fixture
def tls_paths(tmp_path: Path) -> tuple[Path, Path]:
    return _openssl_self_signed_pair(tmp_path)


def _sample_envelope(label: str = "tv_power") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "label": label,
        "carrier_hz": 38000,
        "raw_us": [1000, 500, 1000, 500],
    }


@contextmanager
def _tls_uvicorn_server(
    monkeypatch: pytest.MonkeyPatch,
    api_key: str,
    db_path: Path,
    tls_paths: tuple[Path, Path],
    *,
    disable_openapi: bool = False,
) -> Iterator[tuple[str, ssl.SSLContext]]:
    """Threaded Uvicorn HTTPS server; yields ``(base_url, ssl_context_for_clients)``."""
    cert, key = tls_paths
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    monkeypatch.setenv("IRPETE_API_KEY", api_key)
    monkeypatch.setenv("IRPETE_DB_PATH", str(db_path))
    monkeypatch.setenv("IRPETE_HOST", "127.0.0.1")
    monkeypatch.setenv("IRPETE_PORT", str(port))
    monkeypatch.setenv("IRPETE_TLS_CERTFILE", str(cert))
    monkeypatch.setenv("IRPETE_TLS_KEYFILE", str(key))
    if disable_openapi:
        monkeypatch.setenv("IRPETE_DISABLE_OPENAPI", "1")
    else:
        monkeypatch.delenv("IRPETE_DISABLE_OPENAPI", raising=False)

    settings = load_settings()
    config = uvicorn.Config(
        create_app(settings),
        **uvicorn_kwargs(settings),
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=str(cert))
    try:
        _wait_tcp("127.0.0.1", port)
        yield f"https://127.0.0.1:{port}", ctx
    finally:
        server.should_exit = True
        thread.join(timeout=15)


def test_uvicorn_kwargs_includes_ssl_when_configured(
    settings: Settings, tls_paths: tuple[Path, Path]
) -> None:
    cert, key = tls_paths
    s = replace(settings, tls_certfile=cert, tls_keyfile=key)
    kw = uvicorn_kwargs(s)
    assert kw["ssl_certfile"] == str(cert)
    assert kw["ssl_keyfile"] == str(key)


def test_uvicorn_kwargs_plain_http(settings: Settings) -> None:
    s = replace(settings, tls_certfile=None, tls_keyfile=None)
    kw = uvicorn_kwargs(s)
    assert "ssl_certfile" not in kw


def test_https_health_ok_wrong_and_missing_bearer_401(
    api_key: str,
    db_path: Path,
    tls_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Maps to LAN ``curl`` checks: TLS verify + Bearer required (Stage 3 verification)."""
    with _tls_uvicorn_server(
        monkeypatch, api_key, db_path, tls_paths
    ) as (base, ctx):
        with httpx.Client(verify=ctx, trust_env=False, timeout=5.0) as client:
            missing = client.get(f"{base}/v1/health")
            assert missing.status_code == 401
            assert missing.headers.get("www-authenticate", "").lower().startswith(
                "bearer"
            )

            ok = client.get(
                f"{base}/v1/health",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            assert ok.status_code == 200
            assert ok.json() == {"status": "ok"}

            bad = client.get(
                f"{base}/v1/health",
                headers={"Authorization": "Bearer wrong"},
            )
            assert bad.status_code == 401


def test_https_post_get_signals_roundtrip(
    api_key: str,
    db_path: Path,
    tls_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures TLS terminates correctly for JSON body routes, not only ``/v1/health``."""
    headers = {"Authorization": f"Bearer {api_key}"}
    body = _sample_envelope("tls_roundtrip")
    with _tls_uvicorn_server(
        monkeypatch, api_key, db_path, tls_paths
    ) as (base, ctx):
        with httpx.Client(verify=ctx, trust_env=False, timeout=5.0) as client:
            p = client.post(f"{base}/v1/signals", json=body, headers=headers)
            assert p.status_code == 200
            assert p.json()["label"] == "tls_roundtrip"

            g = client.get(f"{base}/v1/signals/tls_roundtrip", headers=headers)
            assert g.status_code == 200
            assert g.json()["carrier_hz"] == 38000


def test_https_openapi_disabled_via_env(
    api_key: str,
    db_path: Path,
    tls_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _tls_uvicorn_server(
        monkeypatch, api_key, db_path, tls_paths, disable_openapi=True
    ) as (base, ctx):
        with httpx.Client(verify=ctx, trust_env=False, timeout=5.0) as client:
            assert client.get(f"{base}/docs").status_code == 404
            assert client.get(f"{base}/openapi.json").status_code == 404
            assert (
                client.get(
                    f"{base}/v1/health",
                    headers={"Authorization": f"Bearer {api_key}"},
                ).status_code
                == 200
            )
