# Cross-language conformance

A rate limiter is only trustworthy across a polyglot fleet if every implementation
makes the *same* decision for the same request. This directory is the contract that
guarantees it.

## What's here

- **`vectors.json`** — for a fixed configuration and a fixed timeline of request
  timestamps, the exact allow(1)/reject(0) decision each of the five strategies makes.
- **`generate.py`** — regenerates the vectors from the Python reference. Run it only
  when a strategy's decision rule intentionally changes.

## The contract

Each language port ships a conformance test that replays the timeline through every
strategy and asserts it reproduces the committed decision vector. If any port
disagrees, CI fails.

| Port | Conformance test |
|------|------------------|
| Python | `python/tests/test_conformance.py` |
| Go | `go/conformance_test.go` |
| Rust | `rust/tests/conformance.rs` |
| C# | `csharp/tests/ConformanceTests.cs` |
| Java | `java/.../ConformanceTest.java` |
| TypeScript | `web/src/core/conformance.test.ts` |

## Why decisions are portable

Every limiter takes the current time as a parameter (no reading the clock) and computes
its decision with **integer arithmetic only**: token/leak levels are fixed-point
integers (scaled by 1000), and the sliding-window-counter compares its weighted
estimate by cross-multiplication instead of dividing. No floating point means no
per-language rounding, so the decision vectors are identical byte-for-byte.
