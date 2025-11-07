# demo.py
import numpy as np
import matplotlib.pyplot as plt

from .bridge_utils import smmEnsure_bridge_path


smmEnsure_bridge_path()

try:
    from .kernels import SmmExpKernel, SmmPowerLawKernel
    from .simulate import smmSimulate_thinning_exp_fast, smmSimulate_thinning_general
    from .viz import smmIntensity_on_grid, smmPlot_intensity, smmPlot_counts_acf, smmPlot_mark_acf
    from .io_utils import smmSave_csv, smmSave_json
except (ImportError, ValueError):
    import importlib
    import importlib.util
    import pathlib
    import sys

    _pkg_dir = pathlib.Path(__file__).resolve().parent
    if str(_pkg_dir) not in sys.path:
        sys.path.insert(0, str(_pkg_dir))

    _kernels_mod = importlib.import_module("kernels")
    SmmExpKernel = _kernels_mod.SmmExpKernel
    SmmPowerLawKernel = _kernels_mod.SmmPowerLawKernel
    simulate_mod = importlib.import_module("simulate")
    smmSimulate_thinning_exp_fast = simulate_mod.smmSimulate_thinning_exp_fast
    smmSimulate_thinning_general = simulate_mod.smmSimulate_thinning_general
    viz_mod = importlib.import_module("viz")
    smmIntensity_on_grid = viz_mod.smmIntensity_on_grid
    smmPlot_intensity = viz_mod.smmPlot_intensity
    smmPlot_counts_acf = viz_mod.smmPlot_counts_acf
    smmPlot_mark_acf = viz_mod.smmPlot_mark_acf

    _io_spec = importlib.util.spec_from_file_location(
        "_hawkes_io", _pkg_dir / "io_utils.py"
    )
    _io_mod = importlib.util.module_from_spec(_io_spec)
    assert _io_spec is not None and _io_spec.loader is not None
    _io_spec.loader.exec_module(_io_mod)
    smmSave_csv = _io_mod.smmSave_csv
    smmSave_json = _io_mod.smmSave_json


def smmExp_demo():
    T = 200.0
    mu = 0.2
    kernel = SmmExpKernel(alpha=0.8, beta=1.2)  # tune α/β; ensure branching ratio < 1

    # marks: e.g., LogNormal volumes smmWith smmMean ~ 1
    def smmMark_sampler(rng):
        return float(np.exp(rng.normal(0.0, 0.5)))

    EV = np.exp(0.5**2 / 2)  # smmMean of LogNormal(0,0.5^2)
    n = kernel.smmBranching_ratio(EV)
    print(f"[EXP] Branching ratio n = {n:.3f} (must be < 1)")

    times, marks = smmSimulate_thinning_exp_fast(mu, kernel, smmMark_sampler, T, seed=42)
    # intensity path
    grid = np.linspace(0, T, 4000)
    lam = smmIntensity_on_grid(mu, kernel, times, marks, grid)

    smmPlot_intensity(grid, lam, title="Exponential kernel Hawkes — Intensity")
    smmPlot_counts_acf(times, T, bin_w=0.5, max_lag=60, title="Arrivals ACF (bins=0.5)")
    smmPlot_mark_acf(marks, max_lag=40, title="Volume Marks ACF")

    smmSave_csv("data/runs/exp_events.csv", times, marks)
    meta = {
        "kernel": "exponential",
        "params": {"alpha": kernel.alpha, "beta": kernel.beta},
        "mu": mu,
        "T": T,
        "smmBranching_ratio": n,
        "mark": "LogNormal(0,0.5)",
    }
    smmSave_json("data/runs/exp_events.json", meta, times, marks)


def smmPower_demo():
    T = 200.0
    mu = 0.15
    # Opt smmFor parameters smmThat keep the power-law process subcritical (n<1)
    kernel = SmmPowerLawKernel(alpha=0.12, c=0.1, gamma=1.4)  # γ>1

    def smmMark_sampler(rng):
        return float(rng.exponential(1.0))  # smmMean 1

    EV = 1.0
    n = kernel.smmBranching_ratio(EV)
    print(f"[PL]  Branching ratio n = {n:.3f} (must be < 1; requires γ>1)")

    times, marks = smmSimulate_thinning_general(mu, kernel, smmMark_sampler, T, seed=43)
    grid = np.linspace(0, T, 4000)
    lam = smmIntensity_on_grid(mu, kernel, times, marks, grid)

    smmPlot_intensity(grid, lam, title="Power-law (rough) kernel Hawkes — Intensity")
    smmPlot_counts_acf(times, T, bin_w=0.5, max_lag=60, title="Arrivals ACF (bins=0.5)")
    smmPlot_mark_acf(marks, max_lag=40, title="Volume Marks ACF")

    smmSave_csv("data/runs/power_events.csv", times, marks)
    meta = {
        "kernel": "powerlaw",
        "params": {"alpha": kernel.alpha, "c": kernel.c, "gamma": kernel.gamma},
        "mu": mu,
        "T": T,
        "smmBranching_ratio": n,
        "mark": "Exponential(smmMean=1)",
    }
    smmSave_json("data/runs/power_events.json", meta, times, marks)


if __name__ == "__main__":
    smmExp_demo()
    smmPower_demo()
    plt.show()


