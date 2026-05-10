"""
JSON envelope validation for IR signal payloads.

**Mark-first normalization (Stage 1):** IRremoteESP8266 `sendRaw` expects the
first entry to be a *mark* (on) duration. TSOP-class captures sometimes begin
with a long inter-message *space* (off) gap. On ``POST /v1/signals``, if the
first duration exceeds ``LEADING_GAP_US`` (50 ms), it is treated as a leading
idle gap and removed once so the stored payload starts with a mark. Shorter
leading values are kept (caller should capture mark-first or accept stored
semantics as-is for short gaps).
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LABEL_PATTERN = re.compile(r"^[a-z0-9_\-]{1,64}$")

# ESP8266 RAM / JSON size guard (aligned with Stage 1 limits).
MAX_RAW_ELEMENTS = 512
MIN_RAW_ELEMENTS = 2
# Per pulse in microseconds (fits uint16 on Pete).
MIN_PULSE_US = 1
MAX_PULSE_US = 65535

CARRIER_MIN_HZ = 30_000
CARRIER_MAX_HZ = 60_000

# Leading idle gap: strip once on POST if mark-first normalization needs it.
LEADING_GAP_US = 50_000

SCHEMA_VERSION_V1 = 1


def normalize_raw_us_mark_first(raw_us: list[int]) -> list[int]:
    """Return a mark-first ``raw_us`` list (see module docstring)."""
    if not raw_us:
        return raw_us
    out = list(raw_us)
    if len(out) >= 2 and out[0] > LEADING_GAP_US:
        out = out[1:]
    return out


class Envelope(BaseModel):
    """Canonical v1 signal envelope (wire + DB)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: int = Field(..., ge=1)
    label: str
    carrier_hz: int
    raw_us: list[int]
    repeat: int | None = None
    notes: str | None = None

    @field_validator("label")
    @classmethod
    def label_charset(cls, v: str) -> str:
        if not LABEL_PATTERN.fullmatch(v):
            raise ValueError(
                "label must match ^[a-z0-9_\\-]{1,64}$ (lowercase letters, digits, underscore, hyphen)"
            )
        return v

    @field_validator("carrier_hz")
    @classmethod
    def carrier_bounds(cls, v: int) -> int:
        if not (CARRIER_MIN_HZ <= v <= CARRIER_MAX_HZ):
            raise ValueError(
                f"carrier_hz must be between {CARRIER_MIN_HZ} and {CARRIER_MAX_HZ}"
            )
        return v

    @field_validator("raw_us")
    @classmethod
    def raw_pulse_bounds(cls, v: list[int]) -> list[int]:
        if not (MIN_RAW_ELEMENTS <= len(v) <= MAX_RAW_ELEMENTS):
            raise ValueError(
                f"raw_us must have between {MIN_RAW_ELEMENTS} and {MAX_RAW_ELEMENTS} elements"
            )
        for i, x in enumerate(v):
            if not (MIN_PULSE_US <= x <= MAX_PULSE_US):
                raise ValueError(
                    f"raw_us[{i}] must be between {MIN_PULSE_US} and {MAX_PULSE_US} microseconds"
                )
        return v

    @field_validator("repeat")
    @classmethod
    def repeat_non_negative(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v < 0:
            raise ValueError("repeat must be >= 0 when provided")
        return v

    @model_validator(mode="after")
    def schema_version_supported(self) -> Envelope:
        if self.schema_version != SCHEMA_VERSION_V1:
            raise ValueError(f"unsupported schema_version {self.schema_version}; only {SCHEMA_VERSION_V1} is supported")
        return self


def validate_envelope(data: dict[str, Any], *, normalize: bool = True) -> Envelope:
    """
    Parse and validate a dict into an :class:`Envelope`.

    When ``normalize`` is True (default for HTTP POST), ``raw_us`` is normalized
    to mark-first per :func:`normalize_raw_us_mark_first` before bounds checks.
    """
    payload = dict(data)
    raw = payload.get("raw_us")
    if normalize and isinstance(raw, list):
        try:
            ints = [int(x) for x in raw]
        except (TypeError, ValueError) as e:
            raise ValueError("raw_us elements must be integers") from e
        payload["raw_us"] = normalize_raw_us_mark_first(ints)

    return Envelope.model_validate(payload)
