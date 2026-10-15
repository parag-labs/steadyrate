// Package steadyrate implements five rate-limiting strategies behind one interface:
// token bucket, leaky bucket, fixed window, sliding window log, and sliding window
// counter. Each takes the current time as a parameter and decides with integer
// arithmetic only, so all six language ports agree byte-for-byte (see conformance/).
package steadyrate

// Scale is the fixed-point resolution for the bucket limiters: one whole token is
// Scale units. With Scale == 1000 and time in ms, tokens accrued over elapsedMs at
// rate/sec is exactly elapsedMs*rate scaled units - no floating point.
const Scale = 1000

// Limiter decides whether a request at nowMs is allowed.
type Limiter interface {
	Allow(nowMs int64) bool
}

// TokenBucket refills refillPerSec tokens/sec up to capacity; a request costs one.
type TokenBucket struct {
	capacity     int64
	refillPerSec int64
	tokens       int64
	lastMs       int64
	started      bool
}

func NewTokenBucket(capacity, refillPerSec int) *TokenBucket {
	if capacity < 1 {
		panic("capacity must be at least 1")
	}
	if refillPerSec < 1 {
		panic("refillPerSec must be at least 1")
	}
	return &TokenBucket{
		capacity:     int64(capacity),
		refillPerSec: int64(refillPerSec),
		tokens:       int64(capacity) * Scale,
	}
}

func (t *TokenBucket) Allow(nowMs int64) bool {
	if !t.started {
		t.lastMs = nowMs
		t.started = true
	}
	elapsed := nowMs - t.lastMs
	if elapsed < 0 {
		elapsed = 0
	}
	t.tokens += elapsed * t.refillPerSec
	if max := t.capacity * Scale; t.tokens > max {
		t.tokens = max
	}
	t.lastMs = nowMs
	if t.tokens >= Scale {
		t.tokens -= Scale
		return true
	}
	return false
}

// LeakyBucket is a queue of capacity that leaks leakPerSec requests/sec.
type LeakyBucket struct {
	capacity   int64
	leakPerSec int64
	level      int64
	lastMs     int64
	started    bool
}

func NewLeakyBucket(capacity, leakPerSec int) *LeakyBucket {
	if capacity < 1 {
		panic("capacity must be at least 1")
	}
	if leakPerSec < 1 {
		panic("leakPerSec must be at least 1")
	}
	return &LeakyBucket{capacity: int64(capacity), leakPerSec: int64(leakPerSec)}
}

func (l *LeakyBucket) Allow(nowMs int64) bool {
	if !l.started {
		l.lastMs = nowMs
		l.started = true
	}
	elapsed := nowMs - l.lastMs
	if elapsed < 0 {
		elapsed = 0
	}
	l.level -= elapsed * l.leakPerSec
	if l.level < 0 {
		l.level = 0
	}
	l.lastMs = nowMs
	if l.level+Scale <= l.capacity*Scale {
		l.level += Scale
		return true
	}
	return false
}

// FixedWindow admits at most limit requests per windowMs interval.
type FixedWindow struct {
	limit    int64
	windowMs int64
	window   int64
	count    int64
	started  bool
}

func NewFixedWindow(limit, windowMs int) *FixedWindow {
	if limit < 1 {
		panic("limit must be at least 1")
	}
	if windowMs < 1 {
		panic("windowMs must be at least 1")
	}
	return &FixedWindow{limit: int64(limit), windowMs: int64(windowMs)}
}

func (f *FixedWindow) Allow(nowMs int64) bool {
	window := nowMs / f.windowMs
	if !f.started || window != f.window {
		f.window = window
		f.count = 0
		f.started = true
	}
	if f.count < f.limit {
		f.count++
		return true
	}
	return false
}

// SlidingWindowLog keeps timestamps of allowed requests within the trailing window.
type SlidingWindowLog struct {
	limit    int
	windowMs int64
	log      []int64
}

func NewSlidingWindowLog(limit, windowMs int) *SlidingWindowLog {
	if limit < 1 {
		panic("limit must be at least 1")
	}
	if windowMs < 1 {
		panic("windowMs must be at least 1")
	}
	return &SlidingWindowLog{limit: limit, windowMs: int64(windowMs)}
}

func (s *SlidingWindowLog) Allow(nowMs int64) bool {
	cutoff := nowMs - s.windowMs
	i := 0
	for i < len(s.log) && s.log[i] <= cutoff {
		i++
	}
	s.log = s.log[i:]
	if len(s.log) < s.limit {
		s.log = append(s.log, nowMs)
		return true
	}
	return false
}

// SlidingWindowCounter blends current and previous fixed-window counts by overlap.
type SlidingWindowCounter struct {
	limit    int64
	windowMs int64
	window   int64
	current  int64
	previous int64
	started  bool
}

func NewSlidingWindowCounter(limit, windowMs int) *SlidingWindowCounter {
	if limit < 1 {
		panic("limit must be at least 1")
	}
	if windowMs < 1 {
		panic("windowMs must be at least 1")
	}
	return &SlidingWindowCounter{limit: int64(limit), windowMs: int64(windowMs)}
}

func (s *SlidingWindowCounter) Allow(nowMs int64) bool {
	window := nowMs / s.windowMs
	switch {
	case !s.started:
		s.window = window
		s.started = true
	case window == s.window+1:
		s.previous = s.current
		s.current = 0
		s.window = window
	case window > s.window:
		s.previous = 0
		s.current = 0
		s.window = window
	}
	intoWindow := nowMs - window*s.windowMs
	// estimate+1 <= limit, multiplied through by windowMs to stay integer.
	lhs := s.previous*(s.windowMs-intoWindow) + s.current*s.windowMs + s.windowMs
	if lhs <= s.limit*s.windowMs {
		s.current++
		return true
	}
	return false
}
