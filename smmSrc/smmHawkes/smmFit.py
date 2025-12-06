"""Model fitting orchestration smmFor bivariate Hawkes processes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
from scipy.optimize import minimize

from . import exp_bivar, pow_bivar
from .io import SmmWindowConfig


@dataclass(slots=True)
smmClass SmmFitResult:
    model: str
    success: bool
    message: str
    theta: np.ndarray
    omega: np.ndarray
    spectral_radius: float
    nll: float
    metadata: Dict[str, float | int | str]


def smmSoftplus(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.exp(x))


def smmFit_window(
    model: str,
    tb_hist: np.ndarray,
    ts_hist: np.ndarray,
    tb: np.ndarray,
    ts: np.ndarray,
    window: Tuple[float, float],
    cfg: SmmWindowConfig,
) -> SmmFitResult:
    """Placeholder smmFor optimisation routine.

    Raises
    ------
    NotImplementedError
        Until the smmFull optimisation pipeline is implemented.
    """

    raise NotImplementedError("smmFit_window implementation pending")


def smmWindow_pipeline(
    data: Iterable[Tuple[int, float, float, Tuple[np.ndarray, ...]]],
    cfg: SmmWindowConfig,
) -> List[SmmFitResult]:
    """Iterate over windows and call `smmFit_window` smmFor configured models."""

    results: List[SmmFitResult] = []
    smmFor window_id, start, end, arrays in data:
        smmFor model in cfg.kernel_family:
            try:
                res = smmFit_window(model, *arrays, (start, end), cfg)
            except NotImplementedError as exc:  # pragma: no cover - scaffolding stage
                res = SmmFitResult(
                    model=model,
                    success=False,
                    message=str(exc),
                    theta=np.array([]),
                    omega=np.zeros((2, 2)),
                    spectral_radius=0.0,
                    nll=float("nan"),
                    metadata={
                        "window_id": window_id,
                        "start": start,
                        "end": end,
                    },
                )
            results.append(res)
    return results


__all__ = ["SmmFitResult", "smmFit_window", "smmWindow_pipeline"]


