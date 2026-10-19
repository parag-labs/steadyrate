//! Five rate-limiting strategies behind one trait: token bucket, leaky bucket, fixed
//! window, sliding window log, and sliding window counter. Each takes the current time
//! as an argument and decides with integer arithmetic only, so every language port
//! agrees byte-for-byte (see conformance/).

/// Fixed-point resolution for the bucket limiters: one whole token is SCALE units.
pub const SCALE: i64 = 1000;

/// A rate limiter decides whether a request at `now_ms` is allowed.
pub trait Limiter {
    fn allow(&mut self, now_ms: i64) -> bool;
}

pub struct TokenBucket {
    capacity: i64,
    refill_per_sec: i64,
    tokens: i64,
    last_ms: i64,
    started: bool,
}

impl TokenBucket {
    pub fn new(capacity: i64, refill_per_sec: i64) -> Self {
        assert!(capacity >= 1, "capacity must be at least 1");
        assert!(refill_per_sec >= 1, "refill_per_sec must be at least 1");
        Self {
            capacity,
            refill_per_sec,
            tokens: capacity * SCALE,
            last_ms: 0,
            started: false,
        }
    }
}

impl Limiter for TokenBucket {
    fn allow(&mut self, now_ms: i64) -> bool {
        if !self.started {
            self.last_ms = now_ms;
            self.started = true;
        }
        let elapsed = (now_ms - self.last_ms).max(0);
        self.tokens = (self.tokens + elapsed * self.refill_per_sec).min(self.capacity * SCALE);
        self.last_ms = now_ms;
        if self.tokens >= SCALE {
            self.tokens -= SCALE;
            true
        } else {
            false
        }
    }
}

pub struct LeakyBucket {
    capacity: i64,
    leak_per_sec: i64,
    level: i64,
    last_ms: i64,
    started: bool,
}

impl LeakyBucket {
    pub fn new(capacity: i64, leak_per_sec: i64) -> Self {
        assert!(capacity >= 1, "capacity must be at least 1");
        assert!(leak_per_sec >= 1, "leak_per_sec must be at least 1");
        Self {
            capacity,
            leak_per_sec,
            level: 0,
            last_ms: 0,
            started: false,
        }
    }
}

impl Limiter for LeakyBucket {
    fn allow(&mut self, now_ms: i64) -> bool {
        if !self.started {
            self.last_ms = now_ms;
            self.started = true;
        }
        let elapsed = (now_ms - self.last_ms).max(0);
        self.level = (self.level - elapsed * self.leak_per_sec).max(0);
        self.last_ms = now_ms;
        if self.level + SCALE <= self.capacity * SCALE {
            self.level += SCALE;
            true
        } else {
            false
        }
    }
}

pub struct FixedWindow {
    limit: i64,
    window_ms: i64,
    window: i64,
    count: i64,
    started: bool,
}

impl FixedWindow {
    pub fn new(limit: i64, window_ms: i64) -> Self {
        assert!(limit >= 1, "limit must be at least 1");
        assert!(window_ms >= 1, "window_ms must be at least 1");
        Self {
            limit,
            window_ms,
            window: 0,
            count: 0,
            started: false,
        }
    }
}

impl Limiter for FixedWindow {
    fn allow(&mut self, now_ms: i64) -> bool {
        let window = now_ms.div_euclid(self.window_ms);
        if !self.started || window != self.window {
            self.window = window;
            self.count = 0;
            self.started = true;
        }
        if self.count < self.limit {
            self.count += 1;
            true
        } else {
            false
        }
    }
}

pub struct SlidingWindowLog {
    limit: usize,
    window_ms: i64,
    log: std::collections::VecDeque<i64>,
}

impl SlidingWindowLog {
    pub fn new(limit: usize, window_ms: i64) -> Self {
        assert!(limit >= 1, "limit must be at least 1");
        assert!(window_ms >= 1, "window_ms must be at least 1");
        Self {
            limit,
            window_ms,
            log: std::collections::VecDeque::new(),
        }
    }
}

impl Limiter for SlidingWindowLog {
    fn allow(&mut self, now_ms: i64) -> bool {
        let cutoff = now_ms - self.window_ms;
        while let Some(&front) = self.log.front() {
            if front <= cutoff {
                self.log.pop_front();
            } else {
                break;
            }
        }
        if self.log.len() < self.limit {
            self.log.push_back(now_ms);
            true
        } else {
            false
        }
    }
}

pub struct SlidingWindowCounter {
    limit: i64,
    window_ms: i64,
    window: i64,
    current: i64,
    previous: i64,
    started: bool,
}

impl SlidingWindowCounter {
    pub fn new(limit: i64, window_ms: i64) -> Self {
        assert!(limit >= 1, "limit must be at least 1");
        assert!(window_ms >= 1, "window_ms must be at least 1");
        Self {
            limit,
            window_ms,
            window: 0,
            current: 0,
            previous: 0,
            started: false,
        }
    }
}

impl Limiter for SlidingWindowCounter {
    fn allow(&mut self, now_ms: i64) -> bool {
        let window = now_ms.div_euclid(self.window_ms);
        if !self.started {
            self.window = window;
            self.started = true;
        } else if window == self.window + 1 {
            self.previous = self.current;
            self.current = 0;
            self.window = window;
        } else if window > self.window {
            self.previous = 0;
            self.current = 0;
            self.window = window;
        }
        let into_window = now_ms - window * self.window_ms;
        let lhs = self.previous * (self.window_ms - into_window)
            + self.current * self.window_ms
            + self.window_ms;
        if lhs <= self.limit * self.window_ms {
            self.current += 1;
            true
        } else {
            false
        }
    }
}
