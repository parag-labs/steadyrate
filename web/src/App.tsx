import { useMemo, useState } from "react";
import {
  FixedWindow,
  LeakyBucket,
  type Limiter,
  SlidingWindowCounter,
  SlidingWindowLog,
  type StrategyName,
  STRATEGY_LABELS,
  TokenBucket,
} from "./core/limiters";

type Decision = { t: number; allowed: boolean };

const STRATEGIES: StrategyName[] = [
  "token_bucket",
  "leaky_bucket",
  "fixed_window",
  "sliding_window_log",
  "sliding_window_counter",
];

const ACCENT: Record<StrategyName, string> = {
  token_bucket: "#3b82f6",
  leaky_bucket: "#22c55e",
  fixed_window: "#f59e0b",
  sliding_window_log: "#ef4444",
  sliding_window_counter: "#8b5cf6",
};

const BLURB: Record<StrategyName, string> = {
  token_bucket: "Absorbs a burst up to capacity, then settles to the refill rate.",
  leaky_bucket: "Smooths the burst into a steady trickle out.",
  fixed_window: "Simple — but note the double burst across the window edge.",
  sliding_window_log: "Exact: never more than the limit in any trailing window.",
  sliding_window_counter: "Near-exact at O(1) memory — the production default.",
};

// Build a fresh limiter for a strategy given the shared limit + window.
function make(strategy: StrategyName, limit: number, windowMs: number): Limiter {
  const refill = Math.max(1, Math.round((limit * 1000) / windowMs));
  switch (strategy) {
    case "token_bucket":
      return new TokenBucket(limit, refill);
    case "leaky_bucket":
      return new LeakyBucket(limit, refill);
    case "fixed_window":
      return new FixedWindow(limit, windowMs);
    case "sliding_window_log":
      return new SlidingWindowLog(limit, windowMs);
    case "sliding_window_counter":
      return new SlidingWindowCounter(limit, windowMs);
  }
}

// A request timeline: `steady` requests spread across the window, plus a `burst` of
// requests fired all at once at `burstAt` ms.
function buildTimeline(
  windowMs: number,
  steadyPerWindow: number,
  windows: number,
  burst: number,
  burstAt: number,
): number[] {
  const ts: number[] = [];
  const total = windowMs * windows;
  const gap = steadyPerWindow > 0 ? (windowMs / steadyPerWindow) : total + 1;
  for (let t = 0; t < total; t += gap) ts.push(Math.round(t));
  for (let i = 0; i < burst; i++) ts.push(burstAt);
  ts.sort((a, b) => a - b);
  return ts;
}

export function App() {
  const [limit, setLimit] = useState(10);
  const [windowMs] = useState(1000);
  const [steady, setSteady] = useState(6);
  const [burst, setBurst] = useState(12);

  const timeline = useMemo(
    () => buildTimeline(windowMs, steady, 3, burst, windowMs), // burst lands at the window edge
    [windowMs, steady, burst],
  );

  const results = useMemo(() => {
    const out: Record<StrategyName, Decision[]> = {} as Record<StrategyName, Decision[]>;
    for (const s of STRATEGIES) {
      const lim = make(s, limit, windowMs);
      out[s] = timeline.map((t) => ({ t, allowed: lim.allow(t) }));
    }
    return out;
  }, [timeline, limit, windowMs]);

  const total = timeline.length;

  return (
    <div className="app">
      <header>
        <div className="brand"><span className="dot" /> steadyrate</div>
        <h1>Five ways to answer: allow this request, or reject it?</h1>
        <p className="lede">
          The same stream of {total} requests — a steady trickle plus a burst fired right
          at a window boundary — run through all five limiters at a limit of{" "}
          <b>{limit}/sec</b>. Watch how each one accepts (filled) or rejects (hollow),
          and how many it lets through.
        </p>
      </header>

      <div className="controls">
        <label>
          Limit / sec: <b>{limit}</b>
          <input type="range" min={2} max={20} value={limit} onChange={(e) => setLimit(+e.target.value)} />
        </label>
        <label>
          Steady req / window: <b>{steady}</b>
          <input type="range" min={0} max={15} value={steady} onChange={(e) => setSteady(+e.target.value)} />
        </label>
        <label>
          Burst size: <b>{burst}</b>
          <input type="range" min={0} max={25} value={burst} onChange={(e) => setBurst(+e.target.value)} />
        </label>
      </div>

      <div className="strategies">
        {STRATEGIES.map((s) => {
          const decisions = results[s];
          const accepted = decisions.filter((d) => d.allowed).length;
          const pct = total > 0 ? Math.round((accepted / total) * 100) : 0;
          return (
            <div className="strategy" key={s} style={{ borderColor: ACCENT[s] }}>
              <div className="s-head">
                <span className="s-name">{STRATEGY_LABELS[s]}</span>
                <span className="s-count" style={{ color: ACCENT[s] }}>
                  {accepted}/{total} accepted · {pct}%
                </span>
              </div>
              <div className="s-blurb">{BLURB[s]}</div>
              <div className="ticks">
                {decisions.map((d, i) => (
                  <span
                    key={i}
                    className={d.allowed ? "tick on" : "tick off"}
                    style={d.allowed ? { background: ACCENT[s], borderColor: ACCENT[s] } : { borderColor: ACCENT[s] }}
                    title={`t=${d.t}ms ${d.allowed ? "allowed" : "rejected"}`}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <footer>
        <span>
          Same core in Python · Go · Rust · C# · Java · TypeScript — decisions here are
          identical to all six ports.
        </span>
        <a href="https://github.com/parag-labs/steadyrate">Source →</a>
      </footer>
    </div>
  );
}
