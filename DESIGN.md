# steadyrate: design notes

Status: accepted
Author: Parag Sawant

Why the library looks the way it does. Rate limiting is one of those topics where the
naive version (a counter per window) is five lines and subtly wrong at the edges, so
this is the reasoning I'd want a reviewer to push on.

## Goals

1. Implement the five classic strategies behind one `allow(now_ms) -> bool` interface,
   so they're directly comparable.
2. Make every decision **deterministic and portable** — identical across Python, Go,
   Rust, C#, Java, and TypeScript for the same inputs.
3. Make the trade-offs *visible*, not just described — hence the visualizer.

## The key decision: integer-only, time-injected

Two choices make the cross-language conformance possible.

**Inject the clock.** Every limiter takes `now_ms` as an argument instead of calling
the system clock. That's what makes a decision a pure function of (config, request
timeline), so the same timeline produces the same allow/reject vector everywhere, and
tests don't depend on wall-clock timing.

**No floating point in decisions.** A token bucket naturally wants fractional tokens
(refill 2.5 tokens...), and floats round differently across languages — which would
break byte-for-byte conformance. So token and leak levels are held in **fixed-point
integers** scaled by 1000: one token is 1000 units, and tokens accrued over
`elapsed_ms` at `rate`/sec is exactly `elapsed_ms * rate` units (since the scale and
the ms-per-second factor both being 1000 cancel). The sliding-window counter's weighted
estimate — `previous * overlap + current` — is compared by **cross-multiplying** by the
window width instead of dividing, so that decision is integer-only too.

The result: the conformance vectors in `conformance/` pin every strategy's decisions,
and all six ports reproduce them exactly.

## The strategies and their trade-offs

- **Token bucket** — allows bursts up to the capacity, then throttles to the refill
  rate. The default when you want to *permit* bursts.
- **Leaky bucket** — a queue draining at a constant rate; smooths bursts into a steady
  output. The default when you want to *flatten* bursts.
- **Fixed window** — one counter per interval. Simplest and fastest, but allows up to
  2x the limit across a window boundary (the classic flaw).
- **Sliding window log** — keeps timestamps and counts those in the trailing window.
  Exact, and it fixes the boundary burst — but memory grows with traffic.
- **Sliding window counter** — blends the current and previous window counts by
  overlap. Near-exact (a few percent, see BENCHMARKS) at O(1) memory. The usual
  production choice.

## Non-goals

- **Not distributed.** These are single-process limiters. A distributed limiter shares
  state in Redis or similar; the algorithms here are the per-node logic that would sit
  on top of that, not the coordination.
- **No concurrency inside a limiter.** Each instance assumes single-threaded access (or
  external locking). That keeps the reference readable; production wrappers add the
  synchronization.
- **Not a token-cost API.** Every request costs one unit. Weighted requests (a big
  request costing N tokens) are a natural extension, left out to keep the contract
  simple.
