import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  FixedWindow,
  LeakyBucket,
  type Limiter,
  SlidingWindowCounter,
  SlidingWindowLog,
  TokenBucket,
} from "./limiters";

const here = dirname(fileURLToPath(import.meta.url));
const vectors = JSON.parse(
  readFileSync(resolve(here, "../../../conformance/vectors.json"), "utf-8"),
);

function build(strategy: string, p: Record<string, number>): Limiter {
  switch (strategy) {
    case "token_bucket":
      return new TokenBucket(p.capacity, p.refill_per_sec);
    case "leaky_bucket":
      return new LeakyBucket(p.capacity, p.leak_per_sec);
    case "fixed_window":
      return new FixedWindow(p.limit, p.window_ms);
    case "sliding_window_log":
      return new SlidingWindowLog(p.limit, p.window_ms);
    case "sliding_window_counter":
      return new SlidingWindowCounter(p.limit, p.window_ms);
    default:
      throw new Error(strategy);
  }
}

describe("conformance", () => {
  it("all strategies match the vectors", () => {
    const timeline: number[] = vectors.timeline_ms;
    for (const c of vectors.cases) {
      const lim = build(c.strategy, c.params);
      const got = timeline.map((t) => (lim.allow(t) ? 1 : 0));
      expect(got, c.strategy).toEqual(c.decisions);
    }
  });
});
