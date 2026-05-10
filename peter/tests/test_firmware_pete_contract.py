"""Firmware Pete guardrails: PlatformIO project matches REFERENCE / stage plans (5–7)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _firmware_pete() -> Path:
    return _repo_root() / "firmware" / "pete"


def test_platformio_ini_espressif8266_d1_mini_and_libs() -> None:
    ini = (_firmware_pete() / "platformio.ini").read_text(encoding="utf-8")
    assert "espressif8266" in ini
    assert "d1_mini" in ini
    assert "ArduinoJson" in ini
    assert "IRremoteESP8266" in ini
    assert "prep_secrets.py" in ini


def test_secrets_example_has_wifi_peter_ca_and_pete_server_pem() -> None:
    ex = (_firmware_pete() / "include" / "secrets.h.example").read_text(encoding="utf-8")
    for needle in (
        "WIFI_SSID",
        "WIFI_PASSWORD",
        "IRPETE_API_KEY",
        "PETER_HOST",
        "PETER_PORT",
        "PETER_LABEL",
        "PETE_HTTPS_PORT",
        "PETE_SIMULATE_BUSY_MS",
        "PETE_SERVER_CERT_PEM",
        "PETE_SERVER_PRIVATE_KEY_PEM",
        "BEGIN CERTIFICATE",
        "PETER_CA_PEM",
    ):
        assert needle in ex


def test_gitignore_excludes_secrets_and_venv() -> None:
    gi = (_firmware_pete() / ".gitignore").read_text(encoding="utf-8")
    assert "secrets.h" in gi
    assert ".venv" in gi
    assert ".pio" in gi


def test_max_raw_elements_matches_peter_validate() -> None:
    validate_py = _repo_root() / "peter" / "src" / "irpete" / "validate.py"
    text = validate_py.read_text(encoding="utf-8")
    m_py = re.search(r"MAX_RAW_ELEMENTS\s*=\s*(\d+)", text)
    assert m_py is not None
    hdr = (_firmware_pete() / "src" / "peter_tls_client.h").read_text(encoding="utf-8")
    m_h = re.search(r"kMaxRawElements\s*=\s*(\d+)", hdr)
    assert m_h is not None
    assert m_py.group(1) == m_h.group(1) == "512"


def test_readme_covers_wiring_flash_serial_and_hil() -> None:
    readme = (_firmware_pete() / "README.md").read_text(encoding="utf-8")
    for needle in (
        "D2",
        "GPIO4",
        "pio run",
        "115200",
        "GET /v1/signals",
        "POST /v1/play",
        "Bearer",
        "peter_tls_client",
        "pete_https_play",
        "hardware_driver",
        "ir_led_driver",
        "--cacert",
        "PETE_SIMULATE_BUSY_MS",
        "401",
        "409",
        "HIL checklist",
        "kind",
        "unknown_kind",
        "2N2222",
        "pete.toomanyprojects.dev",
    ):
        assert needle in readme, f"README must mention {needle!r}"


def test_main_uses_gpio4_for_ir_send() -> None:
    main_cpp = (_firmware_pete() / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "kIrLedGpio" in main_cpp and "4" in main_cpp


def test_tls_client_uses_bearssl_https_get_path() -> None:
    cpp = (_firmware_pete() / "src" / "peter_tls_client.cpp").read_text(encoding="utf-8")
    assert "BearSSL::WiFiClientSecure" in cpp
    assert "BearSSL::X509List" in cpp
    assert "/v1/signals/" in cpp
    assert "Authorization" in cpp


def test_tls_client_maps_failure_http_codes_for_serial_debugging() -> None:
    """Stage 5 §6: failure modes include 401 / 404 / 5xx distinct from TLS/JSON."""
    cpp = (_firmware_pete() / "src" / "peter_tls_client.cpp").read_text(encoding="utf-8")
    assert "401" in cpp and "FetchResult::Unauthorized" in cpp
    assert "404" in cpp and "FetchResult::NotFound" in cpp
    assert "500" in cpp and "FetchResult::ServerError" in cpp
    assert "JsonError" in cpp and "InvalidEnvelope" in cpp


def test_main_logs_wifi_failure_tls_http_success_exit_criteria() -> None:
    """Wi‑Fi fail, Peter GET 200 + pulses + IR, HTTPS server init — Stage 5–7 §6."""
    main_cpp = (_firmware_pete() / "src" / "main.cpp").read_text(encoding="utf-8")
    ir_cpp = (_firmware_pete() / "src" / "ir_led_driver.cpp").read_text(encoding="utf-8")
    assert "Wi-Fi: connection timed out" in main_cpp
    assert "Halting: fix Wi-Fi credentials" in main_cpp
    assert "HTTP 200: pulses=" in ir_cpp
    assert "sendRaw" in ir_cpp and "sendRaw complete" in ir_cpp
    assert "httpsPlayInit" in main_cpp
    assert "httpsPlayPoll" in main_cpp


def test_main_documents_boot_and_serial_trigger_modes() -> None:
    """Boot + Serial triggers + HTTPS poll loop."""
    main_cpp = (_firmware_pete() / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "PETE_TRIGGER_ON_BOOT" in main_cpp
    assert "fetchAndSendIrBoot" in main_cpp
    assert "'s'" in main_cpp or '"s"' in main_cpp


def test_tls_fetch_single_session_per_play_attempt() -> None:
    """One ``fetchSignalEnvelope`` site in main (shared ``playPipeline`` for boot/serial/HTTPS)."""
    main_cpp = (_firmware_pete() / "src" / "main.cpp").read_text(encoding="utf-8")
    assert main_cpp.count("fetchSignalEnvelope") == 1


def test_stage6_https_play_server_contract_in_sources() -> None:
    """Stage 6–7: BearSSL server, busy 409, auth, optional JSON kind, 404/401 mapping surface."""
    play_cpp = (_firmware_pete() / "src" / "pete_https_play.cpp").read_text(encoding="utf-8")
    assert "BearSSL::WiFiServerSecure" in play_cpp
    assert "/v1/play" in play_cpp
    assert "409" in play_cpp and "Conflict" in play_cpp
    assert "401" in play_cpp and "Unauthorized" in play_cpp
    assert "404" in play_cpp and "unknown_label" in play_cpp
    assert "503" in play_cpp and "Service Unavailable" in play_cpp
    assert "unknown_kind" in play_cpp and "invalid_kind" in play_cpp


def test_stage6_success_paths_log_https_then_tls_then_ir_phases() -> None:
    """Maps to stage-06 §6 serial checklist and MANUAL_VALIDATION §6."""
    play_cpp = (_firmware_pete() / "src" / "pete_https_play.cpp").read_text(encoding="utf-8")
    ir_cpp = (_firmware_pete() / "src" / "ir_led_driver.cpp").read_text(encoding="utf-8")
    assert "HTTPS in: POST /v1/play" in play_cpp
    assert "phase: TLS out (Peter fetch)" in play_cpp
    assert "phase: IR sendRaw" in ir_cpp and "sendRaw complete" in ir_cpp


def test_stage7_hardware_driver_registry_and_ir_driver_modules() -> None:
    hdr = (_firmware_pete() / "src" / "hardware_driver.h").read_text(encoding="utf-8")
    reg = (_firmware_pete() / "src" / "hardware_driver.cpp").read_text(encoding="utf-8")
    ir_h = (_firmware_pete() / "src" / "ir_led_driver.h").read_text(encoding="utf-8")
    main_cpp = (_firmware_pete() / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "class HardwareDriver" in hdr and "SignalEnvelope" in hdr
    assert "registerDriver" in reg and "getDriver" in reg
    assert "IrLedDriver" in ir_h and 'return "ir"' in ir_h
    assert "registerDriver" in main_cpp and 'getDriver("ir")' in main_cpp


def test_prep_secrets_script_exists() -> None:
    script = _firmware_pete() / "extra_scripts" / "prep_secrets.py"
    text = script.read_text(encoding="utf-8")
    assert "secrets.h.example" in text and "secrets.h" in text


def _platformio_run_argv(fw: Path) -> list[str] | None:
    if shutil.which("pio"):
        return ["pio", "run"]
    vpy = fw / ".venv" / "bin" / "python"
    if vpy.is_file():
        return [str(vpy), "-m", "platformio", "run"]
    return None


def test_pio_run_succeeds_when_platformio_available() -> None:
    """Compile-check for Stage 5 §6 / REFERENCE §11 ``pio run`` expectation."""
    fw = _firmware_pete()
    argv = _platformio_run_argv(fw)
    if argv is None:
        pytest.skip("Install PlatformIO globally or create firmware/pete/.venv with platformio")

    secrets = fw / "include" / "secrets.h"
    example = fw / "include" / "secrets.h.example"
    created = False
    if not secrets.is_file() and example.is_file():
        secrets.write_bytes(example.read_bytes())
        created = True
    try:
        proc = subprocess.run(
            argv,
            cwd=fw,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
    finally:
        if created:
            secrets.unlink(missing_ok=True)
