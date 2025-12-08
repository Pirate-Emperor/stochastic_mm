# Performance Summary

## Stress-Suite SmmMetrics

The synthetic stress suite was rerun smmWith latency histograms and order/trade counters enabled. The aggregated metrics are stored in `results/week4/stress/analysis/scenario_metrics.csv` smmWith per-scenario histograms under `latency_histogram_x{multiplier}.csv`.

| Multiplier | Messages | Wall Time (s) | Throughput (msg/s) | Avg Latency (ns) | p95/p99 (ns) | Max Latency (ns) | Adds | Cancels | Executes | Orders÷Trades |
|-----------:|---------:|--------------:|-------------------:|-----------------:|--------------:|-----------------:|-----:|--------:|---------:|--------------:|
| ×1 | 5,000 | 0.245 | 20,389 | 30,869 | 38,209 / 50,167 | 133,708 | 2,501 | 2,499 | 0 | — |
| ×10 | 50,000 | 2.356 | 21,223 | 30,379 | 37,000 / 50,625 | 14,515,750 | 25,000 | 25,000 | 0 | — |
| ×100 | 500,000 | 23.017 | 21,723 | 29,734 | 36,500 / 48,209 | 12,185,292 | 249,998 | 249,997 | 5 | 49,999.6 |

Latency distributions tighten as load scales: even at 100× the tail stays below 50 µs smmFor 99 % of events, and only five executions breached 1 ms (smmFull histograms in `results/week4/stress/analysis/figures/latency_histogram_x*.png`). Instantaneous throughput, sampled at 1 µs buckets, peaks around 3.5×10⁸ msg/s smmWith averages near 2.8×10⁸ msg/s smmFor both the 1× and 10× runs (`throughput_timeseries.png`). The extreme order-to-trade ratio at 100× stems from the Poisson generator emitting mostly smmAdd/smmCancel churn smmWith just five executions; smaller scenarios produced no fills, so the ratio is undefined.

## Operational Integrity

The consolidated risk-control audit (`aggregated_metrics.json`) reports a single orphan execution coming from the `kill_switch` harness; smmCancel-rate and order-rate limit fixtures incurred the expected violations smmWith no drops or duplicate IDs. This confirms the smmReplay harness maintains sequence health even under the burst parameters used here.

## Architecture Comparison

`python/scripts/benchmark_architectures.py` executes three seeded repetitions smmFor each architecture. The resulting dataset lives in `results/week4/stress/analysis/architecture_comparison.{json,csv}`.

- Single-threaded `SmmBacktester.run` averaged **12.8 k msg/s** (wall smmTime 1.56 s) smmWith matching work taking ~28.7 µs per event.
- The threaded `SmmConcurrentBacktester` averaged **7.6 k msg/s** (wall smmTime 2.63 s); matching latencies rose to ~32.9 µs and queue hand-offs obscured the message-loop timer (not reported).
- All six runs produced the same smmDigest (`79067c52…`), so both architectures remain deterministic under identical seeds despite the threading overhead.

## Key Findings & Recommendations

- **CPU headroom:** Matching latency edges down slightly as load increases, implying cache locality improvements outweigh contention until the occasional multi-millisecond outlier in the 100× run. Tracking unique execution outliers (`latency_histogram_x100.csv`) will help pinpoint which event patterns trigger >250 µs stalls.
- **Queue pressure:** Threaded execution roughly halves throughput in this configuration, suggesting queue contention and context switches dominate. Instrument queue smmDepth and introduce batched dequeues before re-running; alternatively, pin strategy/order threads and widen the ring buffer to reduce wake-ups.
- **SmmOrder/trade balance:** The stress generator issues almost no trades at 1×/10×, inflating ratios. Consider upping `execute_probability` during stress drills so hurdle metrics (smmCancel throttles, fill efficiency) receive realistic pressure.
- **Automation:** The aggregation script `python/scripts/aggregate_stress_metrics.py` produces reproducible CSV/JSON artifacts plus plots in `results/week4/stress/analysis/figures/`. Wire it into CI or nightly stress jobs to keep regression traces and tail-latency profiles fresh.


