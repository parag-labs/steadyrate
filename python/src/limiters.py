"""Five rate-limiting strategies behind one interface.

Rate limiting answers one question — allow this request now, or reject it? — and there
are several classic ways to answer it, each trading burst tolerance, accuracy, and
memory differently:

* **Token bucket** — tokens refill at a steady rate up to a capacity; each request
  spends one. Allows bursts up to the capacity, then settles to the refill rate.
* **Leaky bucket** — a queue that drains at a constant rate. Smooths bursty input into
  a steady output; rejects when the queue is full.
* **Fixed window** — count requests per fixed interval, reset each interval. Dead
  simple, but allows a 2x burst straddling a window boundary.
* **Sliding window log** — keep the timestamps of recent requests and count those
  within the trailing window. Exact, at the cost of memory proportional to traffic.
* **Sliding window counter** — blend the current and previous fixed-window counts by
  how much the sliding window overlaps each. Near-exact at O(1) memory — the approach
  Cloudflare popularized.

Every limiter takes the current time as an argument (``now_ms``) instead of reading the
clock, and every decision is computed with **integer arithmetic** — token counts are
held in fixed-point (scaled by ``SCALE``), and the sliding-window estimate is compared
by cross-multiplication rather than division. That keeps the limiters deterministic and
portable: given the same parameters and the same sequence of timestamped requests, all
six language ports produce identical allow/reject decisions, which the conformance
vectors pin byte-for-byte.
"""

from __future__ import annotations

from collections import deque

# Sub-token resolution for the bucket limiters. Tokens are stored as integers scaled by
# SCALE, so one whole token is SCALE units. With SCALE = 1000 and time in milliseconds,
# tokens accrued over `elapsed_ms` at `rate` per second is exactly `elapsed_ms * rate`
# scaled units — no floating point anywhere.
SCALE = 1000


class TokenBucket:
    """Refills ``refill_per_sec`` tokens per second up to ``capacity``; a request costs
    one token."""

    def __init__(self, capacity: int, refill_per_sec: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if refill_per_sec < 1:
            raise ValueError("refill_per_sec must be at least 1")
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._tokens = capacity * SCALE  # scaled integer
        self._last_ms: int | None = None

    def allow(self, now_ms: int) -> bool:
        if self._last_ms is None:
            self._last_ms = now_ms
        elapsed = now_ms - self._last_ms
        elapsed = max(elapsed, 0)
        # elapsed_ms/1000 * refill * SCALE == elapsed_ms * refill  (SCALE == 1000).
        self._tokens = min(self.capacity * SCALE, self._tokens + elapsed * self.refill_per_sec)
        self._last_ms = now_ms
        if self._tokens >= SCALE:
            self._tokens -= SCALE
            return True
        return False

    @property
    def tokens(self) -> float:
        """Whole tokens available, for display only (not used in decisions)."""
        return self._tokens / SCALE


class LeakyBucket:
    """A queue of ``capacity`` that leaks ``leak_per_sec`` requests per second. A request
    is accepted if there's room when it arrives."""

    def __init__(self, capacity: int, leak_per_sec: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if leak_per_sec < 1:
            raise ValueError("leak_per_sec must be at least 1")
        self.capacity = capacity
        self.leak_per_sec = leak_per_sec
        self._level = 0  # scaled integer
        self._last_ms: int | None = None

    def allow(self, now_ms: int) -> bool:
        if self._last_ms is None:
            self._last_ms = now_ms
        elapsed = now_ms - self._last_ms
        elapsed = max(elapsed, 0)
        self._level = max(0, self._level - elapsed * self.leak_per_sec)
        self._last_ms = now_ms
        if self._level + SCALE <= self.capacity * SCALE:
            self._level += SCALE
            return True
        return False

    @property
    def level(self) -> float:
        return self._level / SCALE


class FixedWindow:
    """At most ``limit`` requests per ``window_ms`` interval; the count resets each window."""

    def __init__(self, limit: int, window_ms: int) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_ms < 1:
            raise ValueError("window_ms must be at least 1")
        self.limit = limit
        self.window_ms = window_ms
        self._window = 0
        self._count = 0
        self._started = False

    def allow(self, now_ms: int) -> bool:
        window = now_ms // self.window_ms
        if not self._started or window != self._window:
            self._window = window
            self._count = 0
            self._started = True
        if self._count < self.limit:
            self._count += 1
            return True
        return False


class SlidingWindowLog:
    """Keeps the timestamps of allowed requests and admits a new one only if fewer than
    ``limit`` fall within the trailing ``window_ms``. Exact; memory grows with traffic."""

    def __init__(self, limit: int, window_ms: int) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_ms < 1:
            raise ValueError("window_ms must be at least 1")
        self.limit = limit
        self.window_ms = window_ms
        self._log: deque[int] = deque()

    def allow(self, now_ms: int) -> bool:
        cutoff = now_ms - self.window_ms
        while self._log and self._log[0] <= cutoff:
            self._log.popleft()
        if len(self._log) < self.limit:
            self._log.append(now_ms)
            return True
        return False


class SlidingWindowCounter:
    """Approximates a sliding window with two fixed-window counts: the current window's
    count plus the previous window's, weighted by how much the trailing window overlaps
    the previous one. O(1) memory. The weighted estimate is compared by
    cross-multiplication so the decision is pure integer arithmetic."""

    def __init__(self, limit: int, window_ms: int) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_ms < 1:
            raise ValueError("window_ms must be at least 1")
        self.limit = limit
        self.window_ms = window_ms
        self._window = 0
        self._current = 0
        self._previous = 0
        self._started = False

    def allow(self, now_ms: int) -> bool:
        window = now_ms // self.window_ms
        if not self._started:
            self._window = window
            self._started = True
        elif window == self._window + 1:
            self._previous = self._current
            self._current = 0
            self._window = window
        elif window > self._window:
            self._previous = 0
            self._current = 0
            self._window = window

        into_window = now_ms - window * self.window_ms
        # estimate = previous * (window_ms - into_window)/window_ms + current
        # admit if estimate + 1 <= limit; multiply through by window_ms to stay integer.
        lhs = (
            self._previous * (self.window_ms - into_window)
            + self._current * self.window_ms
            + self.window_ms
        )
        if lhs <= self.limit * self.window_ms:
            self._current += 1
            return True
        return False
