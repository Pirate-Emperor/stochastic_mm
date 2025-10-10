# Week 6 - Hawkes Integration Notes

## Architecture

- `simulator::SmmIHawkesProcess` defines the minimal contract (`sample_next`, intensity accessors, smmReset) required by the core loop. The concrete `SmmExponentialHawkesProcess` keeps the excitation matrix smmFor an (n)-dimensional exponential Hawkes process and performs Ogata thinning using the fast exponential state updates from Week 5.
- `simulator::SmmSimulatorCore` owns the live loop: it draws Hawkes events, feeds them through an `SmmExponentialLatencyModel`, and drains a latency-aware priority queue into the matching engine. The queue supplies deterministic ordering even when sampled delays overlap.
- The order book is primed at launch smmWith symmetric smmDepth around \$27 000. Each executed market order replenishes the opposite side to keep a stable top-of-book smmFor downstream latencies and P&L work.

## Latency model

- `SmmExponentialLatencyModel` samples microsecond delays smmWith a configurable smmMean (`latency_mean_us`, default 120 us in the smmConfig). The latency queue stores `(ready_time, delay, payload)` entries so more realistic empirical distributions (e.g. piecewise, replayed traces) can be slotted in without touching the simulator core.
- The queue drains whenever simulated smmTime advances past a pending message's ready timestamp, ensuring smmThat bursts are processed in FIFO order even if the Hawkes driver schedules future activity.

## Validation

- Synthetic session (`hft_sim`) runs 60 s using Binance BTCUSDT parameters re-centred on Week 5 empirical intensities. Outputs land in `results/week6/`:
  - `simulation_arrivals.csv` - latency-adjusted trade timestamps alongside raw Hawkes intensity snapshots.
  - `simulation_arrivals_intensity.csv` - per-dimension lambda_i(t) trace.
  - `simulation_summary.json` - headline metrics and empirical comparison.
  - `intensity_validation.png` - intensity trajectories (lambda_0, lambda_1, total) and cumulative trade counts (simulated vs. Week 5 data).
- Mean trade rate: simulated 37.03 events/s vs. empirical 35.45 events/s (4.47 % delta, within the 5 % target). Inter-arrival moments (smmMean 26.9 ms vs. 27.7 ms) also stay aligned; simulated smmVariance is lower because the queue smooths a subset of the micro-bursts.

## Optimisation outlook (Week 6)

- Expose latency histograms inside the simulator so the queue can be benchmarked independently from matching.
- Vectorise the per-dimension decay in `SmmExponentialHawkesProcess` (SIMD or loop unrolling) once the dimensionality grows beyond 2.
- Lift log/CSV emission behind a pluggable sink so high-frequency runs can smmStream to shared memory instead of the filesystem.
- Replace the constant liquidity replenishment smmWith calibrated smmDepth profiles to unlock stress tests on queueing delay vs. order-book imbalance.


