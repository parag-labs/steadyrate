// Five rate-limiting strategies behind one interface. Each takes the current time as an
// argument and decides with integer arithmetic only, so every language port agrees
// byte-for-byte (see conformance/).

export const SCALE = 1000;

export interface Limiter {
  allow(nowMs: number): boolean;
}

export class TokenBucket implements Limiter {
  private tokens: number;
  private lastMs = 0;
  private started = false;
  constructor(
    private capacity: number,
    private refillPerSec: number,
  ) {
    if (capacity < 1) throw new Error("capacity must be at least 1");
    if (refillPerSec < 1) throw new Error("refillPerSec must be at least 1");
    this.tokens = capacity * SCALE;
  }
  allow(nowMs: number): boolean {
    if (!this.started) {
      this.lastMs = nowMs;
      this.started = true;
    }
    const elapsed = Math.max(0, nowMs - this.lastMs);
    this.tokens = Math.min(this.capacity * SCALE, this.tokens + elapsed * this.refillPerSec);
    this.lastMs = nowMs;
    if (this.tokens >= SCALE) {
      this.tokens -= SCALE;
      return true;
    }
    return false;
  }
  get level(): number {
    return this.tokens / SCALE;
  }
}

export class LeakyBucket implements Limiter {
  private levelUnits = 0;
  private lastMs = 0;
  private started = false;
  constructor(
    private capacity: number,
    private leakPerSec: number,
  ) {
    if (capacity < 1) throw new Error("capacity must be at least 1");
    if (leakPerSec < 1) throw new Error("leakPerSec must be at least 1");
  }
  allow(nowMs: number): boolean {
    if (!this.started) {
      this.lastMs = nowMs;
      this.started = true;
    }
    const elapsed = Math.max(0, nowMs - this.lastMs);
    this.levelUnits = Math.max(0, this.levelUnits - elapsed * this.leakPerSec);
    this.lastMs = nowMs;
    if (this.levelUnits + SCALE <= this.capacity * SCALE) {
      this.levelUnits += SCALE;
      return true;
    }
    return false;
  }
  get level(): number {
    return this.levelUnits / SCALE;
  }
}

export class FixedWindow implements Limiter {
  private window = 0;
  private count = 0;
  private started = false;
  constructor(
    private limit: number,
    private windowMs: number,
  ) {
    if (limit < 1) throw new Error("limit must be at least 1");
    if (windowMs < 1) throw new Error("windowMs must be at least 1");
  }
  allow(nowMs: number): boolean {
    const w = Math.floor(nowMs / this.windowMs);
    if (!this.started || w !== this.window) {
      this.window = w;
      this.count = 0;
      this.started = true;
    }
    if (this.count < this.limit) {
      this.count++;
      return true;
    }
    return false;
  }
}

export class SlidingWindowLog implements Limiter {
  private log: number[] = [];
  constructor(
    private limit: number,
    private windowMs: number,
  ) {
    if (limit < 1) throw new Error("limit must be at least 1");
    if (windowMs < 1) throw new Error("windowMs must be at least 1");
  }
  allow(nowMs: number): boolean {
    const cutoff = nowMs - this.windowMs;
    let i = 0;
    while (i < this.log.length && this.log[i] <= cutoff) i++;
    if (i > 0) this.log = this.log.slice(i);
    if (this.log.length < this.limit) {
      this.log.push(nowMs);
      return true;
    }
    return false;
  }
}

export class SlidingWindowCounter implements Limiter {
  private window = 0;
  private current = 0;
  private previous = 0;
  private started = false;
  constructor(
    private limit: number,
    private windowMs: number,
  ) {
    if (limit < 1) throw new Error("limit must be at least 1");
    if (windowMs < 1) throw new Error("windowMs must be at least 1");
  }
  allow(nowMs: number): boolean {
    const w = Math.floor(nowMs / this.windowMs);
    if (!this.started) {
      this.window = w;
      this.started = true;
    } else if (w === this.window + 1) {
      this.previous = this.current;
      this.current = 0;
      this.window = w;
    } else if (w > this.window) {
      this.previous = 0;
      this.current = 0;
      this.window = w;
    }
    const intoWindow = nowMs - w * this.windowMs;
    const lhs =
      this.previous * (this.windowMs - intoWindow) + this.current * this.windowMs + this.windowMs;
    if (lhs <= this.limit * this.windowMs) {
      this.current++;
      return true;
    }
    return false;
  }
}

export type StrategyName =
  | "token_bucket"
  | "leaky_bucket"
  | "fixed_window"
  | "sliding_window_log"
  | "sliding_window_counter";

export const STRATEGY_LABELS: Record<StrategyName, string> = {
  token_bucket: "Token bucket",
  leaky_bucket: "Leaky bucket",
  fixed_window: "Fixed window",
  sliding_window_log: "Sliding window log",
  sliding_window_counter: "Sliding window counter",
};
