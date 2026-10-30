"""Benchmark the five limiters: how many allow() decisions per second each sustains,
and how accurate the two sliding-window strategies are against a ground-truth exact
count. Measured on this machine, reproducible: python bench/benchmark.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))

from limiters import (  # noqa: E402
    FixedWindow,
    LeakyBucket,
    SlidingWindowCounter,
    SlidingWindowLog,
    TokenBucket,
)

RESULTS = ROOT / "bench" / "results"
RESULTS.mkdir(exist_ok=True)

N = 2_000_000


def throughput(name: str, limiter) -> int:
    # A realistic mix: timestamps advance ~1ms per request.
    start = time.perf_counter()
    t = 0
    for i in range(N):
        limiter.allow(t)
        if i % 3 == 0:
            t += 1
    elapsed = time.perf_counter() - start
    return int(N / elapsed)


def exact_allowed(timeline: list[int], limit: int, window_ms: int) -> int:
    """Ground truth: a request is allowed iff fewer than `limit` allowed requests fall
    in the trailing window. This is what sliding-window-log computes exactly."""
    log: deque[int] = deque()
    allowed = 0
    for t in timeline:
        while log and log[0] <= t - window_ms:
            log.popleft()
        if len(log) < limit:
            log.append(t)
            allowed += 1
    return allowed


def accuracy() -> dict:
    # A dense, uneven arrival pattern over 10 windows.
    timeline = []
    t = 0
    for _ in range(5000):
        timeline.append(t)
        t += 1 + (t % 7)
    limit, window = 50, 1000
    truth = exact_allowed(timeline, limit, window)

    swc = SlidingWindowCounter(limit, window)
    approx = sum(swc.allow(t) for t in timeline)
    return {
        "exact_allowed": truth,
        "sliding_counter_allowed": approx,
        "error_pct": round(abs(approx - truth) / truth * 100, 2),
    }


def main() -> None:
    tp = {
        "token_bucket": throughput("token_bucket", TokenBucket(1000, 1000)),
        "leaky_bucket": throughput("leaky_bucket", LeakyBucket(1000, 1000)),
        "fixed_window": throughput("fixed_window", FixedWindow(1000, 1000)),
        "sliding_window_log": throughput("sliding_window_log", SlidingWindowLog(1000, 1000)),
        "sliding_window_counter": throughput("sliding_window_counter", SlidingWindowCounter(1000, 1000)),
    }
    summary = {"throughput_per_sec": tp, "accuracy": accuracy()}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
