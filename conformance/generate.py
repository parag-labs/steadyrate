"""Generate conformance/vectors.json — the cross-language contract for the limiters.

For a fixed configuration and a fixed sequence of timestamped requests, each limiter
produces a deterministic allow/reject vector. Every language port must reproduce these
exactly. Run from the repo root: python conformance/generate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))

from limiters import (
    FixedWindow,
    LeakyBucket,
    SlidingWindowCounter,
    SlidingWindowLog,
    TokenBucket,
)

# A shared request timeline in milliseconds: a burst at t=0, a lull, another burst
# straddling the 1000ms window boundary, then a trickle. Exercises burst tolerance,
# refill/leak, and window-edge behaviour.
TIMELINE = [0, 0, 0, 0, 0, 100, 200, 950, 990, 1000, 1010, 1500, 2000, 2500, 3000]


def run(limiter, timeline: list[int]) -> list[int]:
    return [1 if limiter.allow(t) else 0 for t in timeline]


def build() -> dict:
    return {
        "_comment": "Cross-language conformance vectors. See conformance/README.md.",
        "timeline_ms": TIMELINE,
        "cases": [
            {
                "strategy": "token_bucket",
                "params": {"capacity": 5, "refill_per_sec": 2},
                "decisions": run(TokenBucket(5, 2), TIMELINE),
            },
            {
                "strategy": "leaky_bucket",
                "params": {"capacity": 5, "leak_per_sec": 2},
                "decisions": run(LeakyBucket(5, 2), TIMELINE),
            },
            {
                "strategy": "fixed_window",
                "params": {"limit": 5, "window_ms": 1000},
                "decisions": run(FixedWindow(5, 1000), TIMELINE),
            },
            {
                "strategy": "sliding_window_log",
                "params": {"limit": 5, "window_ms": 1000},
                "decisions": run(SlidingWindowLog(5, 1000), TIMELINE),
            },
            {
                "strategy": "sliding_window_counter",
                "params": {"limit": 5, "window_ms": 1000},
                "decisions": run(SlidingWindowCounter(5, 1000), TIMELINE),
            },
        ],
    }


def main() -> None:
    out = ROOT / "conformance" / "vectors.json"
    out.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
