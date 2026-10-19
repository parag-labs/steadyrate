package com.steadyrate;

/**
 * Five rate-limiting strategies behind one interface. Each takes the current time as a
 * parameter and decides with integer arithmetic only, so every language port agrees
 * byte-for-byte (see conformance/).
 */
public final class Limiters {

    /** Fixed-point resolution for the bucket limiters: one whole token is SCALE units. */
    public static final long SCALE = 1000;

    private Limiters() {
    }

    public interface Limiter {
        boolean allow(long nowMs);
    }

    public static final class TokenBucket implements Limiter {
        private final long capacity;
        private final long refillPerSec;
        private long tokens;
        private long lastMs;
        private boolean started;

        public TokenBucket(int capacity, int refillPerSec) {
            if (capacity < 1) throw new IllegalArgumentException("capacity must be at least 1");
            if (refillPerSec < 1) throw new IllegalArgumentException("refillPerSec must be at least 1");
            this.capacity = capacity;
            this.refillPerSec = refillPerSec;
            this.tokens = capacity * SCALE;
        }

        public boolean allow(long nowMs) {
            if (!started) { lastMs = nowMs; started = true; }
            long elapsed = Math.max(0, nowMs - lastMs);
            tokens = Math.min(capacity * SCALE, tokens + elapsed * refillPerSec);
            lastMs = nowMs;
            if (tokens >= SCALE) { tokens -= SCALE; return true; }
            return false;
        }
    }

    public static final class LeakyBucket implements Limiter {
        private final long capacity;
        private final long leakPerSec;
        private long level;
        private long lastMs;
        private boolean started;

        public LeakyBucket(int capacity, int leakPerSec) {
            if (capacity < 1) throw new IllegalArgumentException("capacity must be at least 1");
            if (leakPerSec < 1) throw new IllegalArgumentException("leakPerSec must be at least 1");
            this.capacity = capacity;
            this.leakPerSec = leakPerSec;
        }

        public boolean allow(long nowMs) {
            if (!started) { lastMs = nowMs; started = true; }
            long elapsed = Math.max(0, nowMs - lastMs);
            level = Math.max(0, level - elapsed * leakPerSec);
            lastMs = nowMs;
            if (level + SCALE <= capacity * SCALE) { level += SCALE; return true; }
            return false;
        }
    }

    public static final class FixedWindow implements Limiter {
        private final long limit;
        private final long windowMs;
        private long window;
        private long count;
        private boolean started;

        public FixedWindow(int limit, int windowMs) {
            if (limit < 1) throw new IllegalArgumentException("limit must be at least 1");
            if (windowMs < 1) throw new IllegalArgumentException("windowMs must be at least 1");
            this.limit = limit;
            this.windowMs = windowMs;
        }

        public boolean allow(long nowMs) {
            long w = Math.floorDiv(nowMs, windowMs);
            if (!started || w != window) { window = w; count = 0; started = true; }
            if (count < limit) { count++; return true; }
            return false;
        }
    }

    public static final class SlidingWindowLog implements Limiter {
        private final int limit;
        private final long windowMs;
        private final java.util.ArrayDeque<Long> log = new java.util.ArrayDeque<>();

        public SlidingWindowLog(int limit, int windowMs) {
            if (limit < 1) throw new IllegalArgumentException("limit must be at least 1");
            if (windowMs < 1) throw new IllegalArgumentException("windowMs must be at least 1");
            this.limit = limit;
            this.windowMs = windowMs;
        }

        public boolean allow(long nowMs) {
            long cutoff = nowMs - windowMs;
            while (!log.isEmpty() && log.peekFirst() <= cutoff) log.pollFirst();
            if (log.size() < limit) { log.addLast(nowMs); return true; }
            return false;
        }
    }

    public static final class SlidingWindowCounter implements Limiter {
        private final long limit;
        private final long windowMs;
        private long window;
        private long current;
        private long previous;
        private boolean started;

        public SlidingWindowCounter(int limit, int windowMs) {
            if (limit < 1) throw new IllegalArgumentException("limit must be at least 1");
            if (windowMs < 1) throw new IllegalArgumentException("windowMs must be at least 1");
            this.limit = limit;
            this.windowMs = windowMs;
        }

        public boolean allow(long nowMs) {
            long w = Math.floorDiv(nowMs, windowMs);
            if (!started) { window = w; started = true; }
            else if (w == window + 1) { previous = current; current = 0; window = w; }
            else if (w > window) { previous = 0; current = 0; window = w; }

            long intoWindow = nowMs - w * windowMs;
            long lhs = previous * (windowMs - intoWindow) + current * windowMs + windowMs;
            if (lhs <= limit * windowMs) { current++; return true; }
            return false;
        }
    }
}
