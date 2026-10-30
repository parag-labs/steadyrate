# Benchmarks

Measured on this machine, reproducible: `python bench/benchmark.py`. Absolute numbers
will differ on your hardware — the method and the *relative* picture are the point.

## Throughput

Decisions per second, 2,000,000 `allow()` calls each (pure Python reference):

| Strategy | Decisions/sec |
|----------|--------------:|
| Fixed window | ~3,450,000 |
| Token bucket | ~2,100,000 |
| Sliding window log | ~1,930,000 |
| Leaky bucket | ~1,860,000 |
| Sliding window counter | ~1,200,000 |

Fixed window is the fastest — it's a counter and a division. The bucket limiters do a
little fixed-point arithmetic per call. Sliding window counter does the most work
(two counts plus a weighted comparison) but stays O(1) in memory, unlike the log.

## Accuracy: the sliding window counter vs the exact truth

The sliding-window *counter* approximates the exact sliding window (which the *log*
computes precisely) using O(1) memory. How close is the approximation? Over a dense,
uneven arrival pattern at a limit of 50/window:

| | Allowed |
|--|--------:|
| Exact (sliding log) | 600 |
| Sliding window counter | 573 |
| **Error** | **4.5%** |

So the counter runs a few percent under the exact count here — it's slightly
conservative because it assumes the previous window's requests were spread evenly. That
~4.5% error in exchange for dropping from O(requests) memory to two integers is the
trade every large rate limiter makes, and it's why the sliding window counter is the
common production default.

## Reading these together

There's no free lunch: fixed window is fastest and simplest but allows a 2x burst at
the boundary; the sliding log is exact but its memory grows with traffic; the sliding
counter is the balance — near-exact, O(1) memory, a bit more CPU. The
[visualizer](https://parag-labs.github.io/steadyrate/) shows the burst behaviour these
numbers hint at.
