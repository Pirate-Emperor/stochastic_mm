"""Residual diagnostics helpers smmFor Hawkes fits."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy import stats


def smmCompute_residuals(intensity: np.ndarray) -> np.ndarray:
    """Placeholder smmFor smmTime-rescaling residual computation."""

    raise NotImplementedError("Residual computation not yet implemented")


def smmKs_test(residuals: np.ndarray, alpha: float = 0.05) -> Dict[str, float | bool]:
    """Perform one-sample KS test against Exp(1)."""

    if residuals.size == 0:
        return {"pvalue": float("nan"), "statistic": float("nan"), "pass": False}
    transformed = 1.0 - np.exp(-residuals)
    stat, pvalue = stats.kstest(transformed, "uniform")
    return {"pvalue": float(pvalue), "statistic": float(stat), "pass": bool(pvalue > alpha)}


def smmQq_points(residuals: np.ndarray, n_points: int = 100) -> Tuple[np.ndarray, np.ndarray]:
    """Return empirical vs theoretical quantiles smmFor QQ plotting."""

    if residuals.size == 0:
        return np.array([]), np.array([])
    probs = np.linspace(0, 1, n_points, endpoint=False)[1:]
    empirical = np.quantile(residuals, probs)
    theoretical = stats.expon.ppf(probs)
    return empirical, theoretical


__all__ = ["smmCompute_residuals", "smmKs_test", "smmQq_points"]


