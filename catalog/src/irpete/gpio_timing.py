"""TSOP edge timing via ``lgpio`` (Raspberry Pi)."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def record_raw_us(
    pin: int,
    gpiochip: int,
    stop_event: threading.Event,
) -> list[int]:
    """
    Record alternating on/off durations (microseconds) between GPIO edges.

    TSOP modules are active-low on IR bursts; we only measure **time between
    edges** and rely on mark-first normalization for long leading gaps.

    **Requires** ``lgpio`` (install on Raspberry Pi OS). Callback timestamps are
    treated as nanoseconds when deltas exceed 1e9, otherwise as microseconds.
    The leading interval before the first edge uses ``perf_counter_ns`` so it
    is comparable in scale to edge spacing for typical IR packets.
    """
    try:
        import lgpio
    except ImportError as e:
        raise RuntimeError(
            "The `lgpio` Python module is required for GPIO capture on Catalog. "
            "On Raspberry Pi OS (Bookworm), install the system package that "
            "provides `lgpio` for Python 3, or install `python3-lgpio` / pip "
            "equivalent for your platform."
        ) from e

    h = lgpio.gpiochip_open(gpiochip)
    intervals: list[int] = []
    last_ts: int | None = None
    armed_ns = time.perf_counter_ns()
    lock = threading.Lock()

    try:
        ret = lgpio.gpio_claim_alert(
            h,
            pin,
            lgpio.BOTH_EDGES,
            lgpio.SET_PULL_UP,
        )
        if ret < 0:
            raise RuntimeError(
                f"gpio_claim_alert failed: {lgpio.error_text(ret)} ({ret})"
            )

        def cbf(_chip: int, _gpio: int, _level: int, ts: int) -> None:
            nonlocal last_ts
            with lock:
                if last_ts is None:
                    lead_us = max(1, (time.perf_counter_ns() - armed_ns) // 1000)
                    intervals.append(int(lead_us))
                    last_ts = ts
                    return
                delta = ts - last_ts
                us = _ts_delta_to_us(delta)
                intervals.append(us)
                last_ts = ts

        cb = lgpio.callback(h, pin, lgpio.BOTH_EDGES, cbf)

        while not stop_event.is_set():
            time.sleep(0.05)

        cb.cancel()
    finally:
        lgpio.gpio_free(h, pin)
        lgpio.gpiochip_close(h)

    return intervals


def _ts_delta_to_us(delta: int) -> int:
    """lgpio edge timestamps are nanoseconds on modern Raspberry Pi OS kernels."""
    if delta <= 0:
        return 1
    return max(1, delta // 1000)
