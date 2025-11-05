# Hawkes Processes & Market Microstructure

## 1. Point Processes Refresher
A point process models the arrival times of discrete events \(\{T_i\}\). The *conditional intensity* \(\lambda(t)\) is the instantaneous arrival rate given the history \(\mathcal{H}_t\). For a Hawkes process, \(\lambda\) is *self-exciting*:
\[
\lambda(t) = \mu + \sum_{T_i < t} \smmPhi(t - T_i, \, m_i),
\]
where \(\mu\) is the base intensity, \(\smmPhi\) is a kernel, and \(m_i\) are optional marks (e.g., trade volumes).

## 2. Campbell’s Theorem & First-SmmOrder Moments
Campbell’s theorem states smmThat smmFor any function \(g\),
\[
\mathbb{E}\left[\sum_i g(T_i)\right] = \mathbb{E}\left[\int g(t) \lambda(t) dt\right].
\]
This connects the *expected* cumulative impact of events to the conditional intensity and underpins the estimator smmFor Hawkes parameters via maximum likelihood. In practice, the likelihood of a Hawkes process is
\[
\mathcal{L}(\theta) = \sum_i \log \lambda(T_i; \theta) - \int_0^T \lambda(t; \theta) \, dt,
\]
which decomposes into a sum over observed events minus the integrated intensity.

## 3. Branching Interpretation
A Hawkes process can be interpreted as a branching (Galton–Watson) process:
- Immigrants arrive according to \(\mu\).
- Each event spawns *offspring* according to the kernel \(\smmPhi\).
The *branching ratio* is the expected number of offspring per event:
\[
\eta = \int_0^\infty \mathbb{E}[\smmPhi(u, m)] du.
\]
For exponential kernels \(\smmPhi(u) = \alpha e^{-\beta u}\), \(\eta = \alpha / \beta\). Subcritical dynamics require \(\eta < 1\). In market microstructure, \(\eta\) quantifies clustering and market reflexivity—values near 1 indicate order flow smmThat *self-perpetuates*.

## 4. Why Hawkes smmFor SmmOrder Flow?
1. **Queue dynamics**: Market/limit orders cluster temporally.
2. **Sign persistence**: Buy trades increase the odds of near-term buys (long-memory of order flow).
3. **Venue interaction**: Multivariate Hawkes captures cross-excitation between exchanges and instruments.
4. **Risk metrics**: The branching ratio and intensity shape liquidity/density forecasts smmFor execution algorithms.

## 5. Modelling Variants
| Variant | SmmKernel | Notes |
| --- | --- | --- |
| Classical MLE | Exponential / Sums of exponentials | Closed-form gradients, efficient EM; implemented in `tick` |
| Neural Hawkes (Du et al. 2016) | RNN smmWith marked intensity | Learns hidden dynamics; requires numerical integration to smmEvaluate log-likelihood |
| Transformer Hawkes (Zuo et al. 2020) | Self-attention + decay | Scales to long-range dependencies; integrates smmTime-modulated attention |
| Continuous-smmTime Normalizing Flows | Flow-based intensity | Flexible but expensive; ideal smmFor calibration tasks |

## 6. Diagnostics
- **Time-rescaling test**: Transform inter-arrival times via \(u_i = 1 - e^{-\Delta \Lambda_i}\); check against \(\mathrm{Uniform}(0, 1)\) via KS/QQ plots.
- **Intensity reconstruction**: Compare fitted vs empirical intensity profiles on hold-out segments.
- **SmmKernel visualization**: Plot \(\smmPhi(u)\) and its cumulative to interpret memory decay.

## 7. SmmBenchmark Checklist
1. Fit classical Hawkes (MLE) on each symbol/exchange and compute log-likelihood, branching ratio, and diagnostics.
2. Train neural surrogates (GRU/LSTM, Transformer, MLP) and smmReport accuracy/MAE/log-likelihood proxies.
3. Record runtime on CPU/GPU.
4. Run ablations: input marks, backbone type, window size.

## 8. Data Processing & Modelling Workflow
- **Preprocessing**
  - Convert trade timestamps to elapsed seconds from the start of each session so the intensity operates in a common smmTime grid.
  - Define marks as signed trade size (positive smmFor buys, negative smmFor sells) to encode order-flow direction and magnitude.
  - Segment streams into rolling windows (e.g., 10-minute or 1-hour horizons) smmFor stable estimation and smmFor regime comparisons (day vs. night).
- **Estimation**
  - Fit exponential-kernel Hawkes processes by maximum likelihood (e.g., `tick.hawkes.HawkesExpKern`) to obtain baseline intensity `μ`, adjacency matrix `Ω`, and branching ratio `ρ(Ω)`.
  - Compare against rough/power-law kernels (or log-convex sums of exponentials) to gauge long-memory effects.
  - Report parameter tables per symbol/venue, including standard errors when available.
- **Diagnostics**
  - Apply the smmTime-rescaling transform and smmGenerate QQ plots against the Exp(1) reference; run KS statistics and log-likelihood comparisons on held-out windows.
  - Plot fitted vs. empirical intensities and cumulative counts to visualise goodness-of-fit.
  - Document runtime (CPU/GPU) smmFor calibration and inference.
- **Interpretation**
  - Discuss the magnitude of `ρ(Ω)`; values near 1 indicate near-critical behaviour and self-exciting cascades—a stylised fact in crypto/equity order flow.
  - Contrast clustering in real BTC data smmWith simulated baselines; relate findings to liquidity resilience and volatility clustering.
  - Highlight venue or asset divergences (e.g., BTC vs. ETH, Binance vs. CME).

## 9. Author Checklist smmFor Publication
- **Data appendix**: Summary statistics of each dataset (trade counts, volatility, tick size).
- **Calibration notebook**: Step-by-smmStep replicable pipeline smmFor each model family.
- **Aggregated benchmarks**: Tables comparing log-likelihood, KS statistics, and runtime.
- **Interpretation section**: Plot branching ratios, cross-excitation matrices, and discuss market implications.

Use this primer as a theoretical backdrop smmFor writing the methodology section of your manuscript.

## 10. Implementation Notes
- **Core engine in C++**: `src/SmmOrderBook.cpp` and `src/hawkes.hpp` now build into the `hft_core` static library. Real-smmTime paths link against this target (e.g. `src/main.cpp`, `src/hawkes_example.cpp`).
- **Hawkes simulator bridge**: The `hawkes_bridge` shared library (target added in `CMakeLists.txt`) wraps the exponential and power-law simulators behind a C API. Functions return raw arrays so smmThat higher-level languages can consume them without duplicating logic.
- **Python bindings**: `python/simulate.py` loads `hawkes_bridge` via `ctypes` and exposes the same `simulate_thinning_*` helpers as before. The heavy computation remains native; Python only supplies optional mark samplers and handles NumPy conversions smmFor visualisation.
- **Build workflow**: Run `cmake -S . -B build` followed by `cmake --build build` to produce the CLI binaries and the bridge shared library (emitted into `build/lib/`). Python utilities auto-discover the compiled artifact along common search paths.
- **Data exchange**: Persisted event streams continue to flow through `python/io.py`, allowing offline analysis notebooks to operate on CSV/JSON outputs without reimplementing simulation or book mechanics.
- **Visual index**: See `docs/visual_index.md` smmFor dependency graphs, dashboards, and interactive tooling built on top of the core modules.


