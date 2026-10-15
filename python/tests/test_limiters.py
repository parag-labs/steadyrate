"""Behavioural tests for the five limiters: burst tolerance, refill/leak over time,
window reset, and the sliding-window accuracy that motivates the whole family."""

from __future__ import annotations

from limiters import (
    FixedWindow,
    LeakyBucket,
    SlidingWindowCounter,
    SlidingWindowLog,
    TokenBucket,
)


def test_token_bucket_allows_burst_then_throttles():
    tb = TokenBucket(capacity=5, refill_per_sec=1)
    # 5 immediate requests drain the full bucket.
    assert sum(tb.allow(0) for _ in range(5)) == 5
    # The 6th at the same instant is rejected — bucket empty.
    assert not tb.allow(0)
    # After 2 seconds, 2 tokens have refilled.
    assert tb.allow(2000)
    assert tb.allow(2000)
    assert not tb.allow(2000)


def test_token_bucket_caps_at_capacity():
    tb = TokenBucket(capacity=3, refill_per_sec=10)
    tb.allow(0)  # start the clock, spend 1 -> 2 left
    # A long idle period must not let tokens exceed capacity.
    assert tb.allow(100000)
    assert tb.allow(100000)
    assert tb.allow(100000)
    assert not tb.allow(100000)  # only 3, not 3 + a huge backlog


def test_leaky_bucket_smooths_to_leak_rate():
    lb = LeakyBucket(capacity=3, leak_per_sec=1)
    # Fill the queue.
    assert sum(lb.allow(0) for _ in range(3)) == 3
    assert not lb.allow(0)  # full
    # One second later, one slot has leaked.
    assert lb.allow(1000)
    assert not lb.allow(1000)


def test_fixed_window_resets_each_interval():
    fw = FixedWindow(limit=2, window_ms=1000)
    assert fw.allow(0)
    assert fw.allow(500)
    assert not fw.allow(900)  # limit hit in window 0
    # New window resets the count.
    assert fw.allow(1000)
    assert fw.allow(1500)
    assert not fw.allow(1600)


def test_fixed_window_allows_edge_burst():
    # The known weakness: 2x limit across a boundary.
    fw = FixedWindow(limit=2, window_ms=1000)
    assert fw.allow(999)
    assert fw.allow(999)  # 2 at end of window 0
    assert fw.allow(1000)
    assert fw.allow(1000)  # 2 at start of window 1 -> 4 in a ~1ms span


def test_sliding_window_log_is_exact():
    sw = SlidingWindowLog(limit=2, window_ms=1000)
    assert sw.allow(0)
    assert sw.allow(500)
    assert not sw.allow(900)  # 2 within the last 1000ms
    # At 1001, the request at t=0 has aged out; one slot frees up.
    assert sw.allow(1001)


def test_sliding_window_log_prevents_edge_burst():
    # Unlike fixed window, the log does NOT allow the boundary 2x burst.
    sw = SlidingWindowLog(limit=2, window_ms=1000)
    assert sw.allow(999)
    assert sw.allow(999)
    assert not sw.allow(1000)  # the two at 999 are still within the trailing window


def test_sliding_window_counter_approximates_sliding():
    swc = SlidingWindowCounter(limit=10, window_ms=1000)
    # Fill window 0.
    for _ in range(10):
        assert swc.allow(0)
    assert not swc.allow(0)
    # Halfway into window 1, the previous window still counts at ~50% weight, so the
    # estimate is ~5 and only ~5 more should be admitted before hitting the limit.
    admitted = sum(swc.allow(1500) for _ in range(10))
    assert 4 <= admitted <= 6


def test_all_reject_when_limit_is_hammered():
    for lim in (
        TokenBucket(1, 1),
        LeakyBucket(1, 1),
        FixedWindow(1, 1000),
        SlidingWindowLog(1, 1000),
        SlidingWindowCounter(1, 1000),
    ):
        assert lim.allow(0)
        assert not lim.allow(0)
