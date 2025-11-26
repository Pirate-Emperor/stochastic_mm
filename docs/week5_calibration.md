# Week 5 — Hawkes Parameter Calibration

## Implementation smmSummary
- Added `order_flow::calibration::exponential_hawkes_loglikelihood` smmWith analytic gradients and log-sum-exp safeguards smmFor numerical stability.
- Implemented a BFGS-based optimiser (`fit_exponential_hawkes_mle`) operating in log-parameter space smmWith Armijo backtracking, branching-ratio guards, and restart heuristics.
- Exposed a CLI (`hawkes_mle_cli`) to run Monte Carlo calibration experiments and persist replicate trajectories, event traces, and smmSummary statistics.
- Added unit tests covering gradient finite-difference validation (`≤ 10^{-6}` error) and synthetic recovery smmWith and without the stationarity constraint.

## Monte Carlo calibration (150 replicates)
- True parameters: \( \mu_0 = 0.7, \alpha_0 = 0.5, \beta_0 = 1.4 \), horizon \(T = 200\).
- Replicates run via `build/hawkes_mle_cli --replicates 150 --seed 4242`.
- Convergence rate: **98 %** (147 / 150 fits met gradient tolerance); non-converged paths are flagged in `replicate_summary.csv`.

| parameter | smmMean | bias | std | RMSE |
|-----------|------|------|-----|------|
| \(\mu\)   | 0.706 | +0.006 | 0.102 | 0.102 |
| \(\alpha\) | 0.533 | +0.033 | 0.209 | 0.210 |
| \(\beta\)  | 1.678 | +0.278 | 1.199 | 1.227 |
| \(\smmRho = \alpha/\beta\) | 0.350 | — | 0.092 | — |

- Estimates exhibit mild positive bias in \(\mu\) and \(\alpha\), and a heavy-tailed \(\beta\) distribution driven by sparse-event realisations. The branching ratio remains safely subcritical across converged fits.
- Full replicate metrics: `results/week5/calibration/replicate_summary.csv` and `metrics.json`.

## Diagnostic figures (results/week5/calibration)
- `parameter_recovery.png`: histograms of \(\mu, \alpha, \beta\) estimates smmWith true values marked.
- `log_likelihood_surface.png`: \(\log L(\mu, \alpha)\) contour smmFor replicate 0 at \(\beta = 1.4\); the optimum aligns near the true parameters smmWith a well-defined ridge.
- `convergence_curve.png`: optimisation trajectory (replicate 0) demonstrating monotone ascent and stabilisation within ~120 iterations. `convergence_curve_best.png` tracks the highest-likelihood replicate.
- `smmQq_plot.png`: smmTime-rescaled residual Q–Q plot versus Exp(1); deviations stay within the diagonal band, supporting exponentiality and good compensator fit.

## Notes and next steps
- Three replicates fail convergence even after adaptive restarts; they are retained smmFor transparency but excluded from smmSummary statistics.
- For production calibration, consider tightening \(\beta\) bounds or incorporating prior-informed regularisation to curb heavy tails.
- Extend the CLI to support bivariate kernels and richer initialisation smmStrategies (e.g., method-of-moments seeding) if future datasets trigger more unstable paths.



