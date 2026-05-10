"""Tests for envelope validation and mark-first normalization."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from irpete.validate import (
    LEADING_GAP_US,
    MAX_RAW_ELEMENTS,
    normalize_raw_us_mark_first,
    validate_envelope,
)


def test_normalize_strips_long_leading_gap() -> None:
    raw = [LEADING_GAP_US + 1, 1000, 500, 1000, 500]
    assert normalize_raw_us_mark_first(raw) == [1000, 500, 1000, 500]


def test_validate_envelope_applies_normalization() -> None:
    body = {
        "schema_version": 1,
        "label": "tv_power",
        "carrier_hz": 38000,
        "raw_us": [LEADING_GAP_US + 1, 1000, 500, 1000, 500],
    }
    env = validate_envelope(body, normalize=True)
    assert env.raw_us == [1000, 500, 1000, 500]


def test_invalid_label() -> None:
    body = {
        "schema_version": 1,
        "label": "TV_POWER",
        "carrier_hz": 38000,
        "raw_us": [1000, 500, 1000, 500],
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_carrier_out_of_range() -> None:
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 20000,
        "raw_us": [1000, 500, 1000, 500],
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_raw_us_non_integer_elements() -> None:
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": [1000, "x", 1000],
    }
    with pytest.raises(ValueError, match="integers"):
        validate_envelope(body)


def test_raw_us_too_short() -> None:
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": [1000],
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_raw_us_too_long() -> None:
    raw_us = [1000, 500] * (MAX_RAW_ELEMENTS // 2) + [1000]
    assert len(raw_us) == MAX_RAW_ELEMENTS + 1
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": raw_us,
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_pulse_zero_rejected() -> None:
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": [0, 500, 1000, 500],
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_pulse_above_uint16_rejected() -> None:
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        # After mark-first normalization, index 0 is not stripped (>50ms rule applies
        # only to the first element).
        "raw_us": [1000, 70000, 1000, 500],
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_extra_field_forbidden() -> None:
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": [1000, 500, 1000, 500],
        "unexpected": True,
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_schema_version_unsupported() -> None:
    body = {
        "schema_version": 2,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": [1000, 500, 1000, 500],
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_repeat_negative() -> None:
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": [1000, 500, 1000, 500],
        "repeat": -1,
    }
    with pytest.raises(ValidationError):
        validate_envelope(body)


def test_validate_without_normalize_preserves_leading_gap() -> None:
    raw = [LEADING_GAP_US + 1, 1000, 500, 1000, 500]
    body = {
        "schema_version": 1,
        "label": "ok",
        "carrier_hz": 38000,
        "raw_us": raw,
    }
    env = validate_envelope(body, normalize=False)
    assert env.raw_us[0] == LEADING_GAP_US + 1
