"""The Python reference must reproduce the committed conformance vectors exactly.
Every other language ships the mirror of this test."""

from __future__ import annotations

import json
from pathlib import Path

from limiters import (
    FixedWindow,
    LeakyBucket,
    SlidingWindowCounter,
    SlidingWindowLog,
    TokenBucket,
)

VECTORS = json.loads(
    (Path(__file__).resolve().parents[2] / "conformance" / "vectors.json").read_text(
        encoding="utf-8"
    )
)

BUILDERS = {
    "token_bucket": lambda p: TokenBucket(p["capacity"], p["refill_per_sec"]),
    "leaky_bucket": lambda p: LeakyBucket(p["capacity"], p["leak_per_sec"]),
    "fixed_window": lambda p: FixedWindow(p["limit"], p["window_ms"]),
    "sliding_window_log": lambda p: SlidingWindowLog(p["limit"], p["window_ms"]),
    "sliding_window_counter": lambda p: SlidingWindowCounter(p["limit"], p["window_ms"]),
}


def test_all_strategies_match_vectors():
    timeline = VECTORS["timeline_ms"]
    for case in VECTORS["cases"]:
        limiter = BUILDERS[case["strategy"]](case["params"])
        got = [1 if limiter.allow(t) else 0 for t in timeline]
        assert got == case["decisions"], f"{case['strategy']} drifted"
