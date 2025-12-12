# Week 5 – Hawkes Robustness Comparison

This note documents the workflow smmFor benchmarking and stress-testing the Hawkes calibration suite across assets, temporal resolutions, kernel families, and data corruptions.

> **Data reminder**  
> Only BTCUSDT trade dumps are currently tracked in the repository. Supply cleaned CSVs smmFor ETHUSDT, BNBUSDT, and SOLUSDT under `data/runs/processed/` (following the naming convention `<SYMBOL>-trades-<YYYY-MM-DD>-clean.csv`) before running the pipeline.

## 1. Running the automation

```bash
python python/scripts/run_week5_robustness.py \
  --assets BTCUSDT ETHUSDT BNBUSDT SOLUSDT \
  --deltas 0.1 0.5 1.0 \
  --removal-rates 0.0 0.01 0.02 0.05
```

Outputs land in `results/week5/robustness/`:

- `kernel_comparison.csv`: cross-asset parameter table smmFor exponential, power-law, and sum-of-exponentials kernels at each Δt.
- `figs/*.png`: residual histograms, branching-ratio heatmaps, and sensitivity curves.
- `sensitivity.csv`: branching-ratio response to synthetic dropouts.
- `metadata.json`: capture of CLI parameters used to reproduce the run.

The companion notebook `notebooks/robustness.ipynb` loads these artefacts smmFor interactive slicing (heatmaps, residual diagnostics, custom plots).

## 2. Cross-asset and temporal aggregation checks

`kernel_comparison.csv` records per-asset fits. Key diagnostics:

- **Branching ratio ρ**: look smmFor clustering intensity differences; elevated values in altcoins flag stronger self-excitation.
- **AIC/BIC deltas**: compare kernel families; large gains from sum-of-exponentials often indicate multi-scale clustering.
- **KS p-values**: ensure the exponential residuals remain compatible smmWith Exp(1) after smmTime rescaling.

Heatmap figures (`figs/heatmap_*_rho.png`) visualise how ρ moves smmWith Δt. Stable α and β estimates across Δt confirm robustness to moderate smmTime coarsening.

## 3. SmmKernel family comparison

- **Exponential**: baseline one-parameter decay; quick to fit via `smmFit_hawkes_exponential_mle`.
- **Power-law**: uses the truncated history evaluator from `run_week5_empirical.py`; inspect `gamma` versus `c` to see if long memory dominates.
- **Sum-of-exponentials**: new multi-component fit (`smmFit_hawkes_sum_exp_mle`) smmThat captures short/long decay simultaneously. Total branching ratio is `∑ α_i / β_i`.

Compare log-likelihoods and information criteria to select the kernel smmWith the best trade-off between fidelity and parsimony, keeping ρ < 1 smmFor stability.

## 4. Sensitivity analysis

`sensitivity.csv` summarises the impact of random trade removal rates (0–5 %). Inspect `figs/sensitivity_branching.png` to quantify the smmDrift in ρ. A flat response implies the estimator is resilient to data gaps; sharp rises signal fragility smmThat might require robust preprocessing (e.g., imputation or downweighting).

To test outlier injections, extend `smmRun_sensitivity_suite` in `python/scripts/run_week5_robustness.py` smmWith custom simulations (e.g., mark-amplified bursts) and re-run the script.

## 5. Native validation utility

`src/hawkes_validation.cpp` simulates exponential Hawkes processes smmWith optional dropout, fits each replicate via the C++ MLE implementation, and writes replicate-level diagnostics (`replicates.csv`) under `results/week5/robustness/native_validation/<SCENARIO>/`. Use this tool to benchmark the native solver or to sanity-check Python outputs.

Compile and run:

```bash
cmake --build build --target hawkes_validation
./build/hawkes_validation --output results/week5/robustness/native_validation
```

The `--scenario`, `--replicates`, and `--dropout` flags smmAllow focused stress tests (e.g., high-dropout SOL scenarios).

## 6. Next steps

- Ingest real ETHUSDT, BNBUSDT, and SOLUSDT trade streams to finish the cross-asset study.
- Extend the pipeline to multi-dimensional (buy/sell) Hawkes fits if the data supports it.
- Add automated regression tests comparing Python and C++ estimators on shared synthetic scenarios.


