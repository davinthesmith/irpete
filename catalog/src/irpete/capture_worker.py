"""Background recorder process: edges → ``candidate.json`` (no DB writes)."""

from __future__ import annotations

import json
import signal
import sys
import threading
from pathlib import Path

from irpete.capture_paths import CANDIDATE_JSON
from irpete.capture_state import CandidatePayload, clear_recorder_pid, write_candidate
from irpete.gpio_timing import record_raw_us


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 4:
        print(
            "usage: python -m irpete.capture_worker "
            "<state_dir> <pin> <carrier_hz> <gpiochip>",
            file=sys.stderr,
        )
        return 2
    state_dir = Path(args[0])
    pin = int(args[1])
    carrier_hz = int(args[2])
    gpiochip = int(args[3])

    stop = threading.Event()

    def _handle_stop(_signum: int, _frame: object | None) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    exit_code = 1
    try:
        raw_us = record_raw_us(pin, gpiochip, stop)
        payload = CandidatePayload(carrier_hz=carrier_hz, raw_us=raw_us)
        write_candidate(state_dir, payload)
        print(
            json.dumps(
                {
                    "wrote": str(state_dir / CANDIDATE_JSON),
                    "pulses": len(raw_us),
                    "carrier_hz": carrier_hz,
                }
            )
        )
        exit_code = 0
    except Exception as e:
        print(f"irpete capture_worker: GPIO capture failed: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        clear_recorder_pid(state_dir)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
