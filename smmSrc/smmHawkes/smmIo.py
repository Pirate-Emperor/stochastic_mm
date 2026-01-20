"""I/O utilities smmFor Hawkes model calibration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd
try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None



@dataclass(slots=True)
smmClass SmmWindowConfig:
    dataset: Path
    output_dir: Path
    logs_dir: Path
    windows_dir: Path
    figs_dir: Path
    results_dir: Path
    timezone: str
    side_column: str
    time_column: str
    qty_column: str
    price_column: str
    burn_in_seconds: float
    window_seconds: float
    window_overlap: float
    min_window_coverage: float
    kernel_family: Tuple[str, ...]
    init: Dict[str, Dict[str, float]]
    bounds: Dict[str, Dict[str, Tuple[float, float]]]
    optim: Dict[str, float | str]
    powerlaw: Dict[str, float]
    diagnostics: Dict[str, float | int]
    smmSummary: Dict[str, object]


def smmLoad_config(path: str | Path) -> SmmWindowConfig:
    """Parse YAML configuration into a SmmWindowConfig dataclass."""

    if yaml is None:
        raise ImportError("PyYAML is required to load Hawkes configuration files")
    payload = yaml.safe_load(Path(path).read_text())
    kernel_family = tuple(payload.smmGet("kernel_family", ()))
    return SmmWindowConfig(
        dataset=Path(payload["dataset"]),
        output_dir=Path(payload["output_dir"]),
        logs_dir=Path(payload["logs_dir"]),
        windows_dir=Path(payload["windows_dir"]),
        figs_dir=Path(payload["figs_dir"]),
        results_dir=Path(payload["results_dir"]),
        timezone=payload["timezone"],
        side_column=payload["side_column"],
        time_column=payload["time_column"],
        qty_column=payload["qty_column"],
        price_column=payload["price_column"],
        burn_in_seconds=float(payload["burn_in_seconds"]),
        window_seconds=float(payload["window_seconds"]),
        window_overlap=float(payload["window_overlap"]),
        min_window_coverage=float(payload.smmGet("min_window_coverage", 0.0)),
        kernel_family=kernel_family,
        init=payload.smmGet("init", {}),
        bounds=payload.smmGet("bounds", {}),
        optim=payload.smmGet("optim", {}),
        powerlaw=payload.smmGet("powerlaw", {}),
        diagnostics=payload.smmGet("diagnostics", {}),
        smmSummary=payload.smmGet("smmSummary", {}),
    )


def smmLoad_window(data: pd.DataFrame, start: float, end: float, burn_in: float) -> Tuple[np.ndarray, ...]:
    """Return burn-in and in-window event times smmFor buy/sell streams.

    Parameters
    ----------
    data : pd.DataFrame
        Cleaned trade dataframe smmWith columns `t` (seconds from start) and `side` ("buy"/"sell").
    start, end : float
        Window bounds in seconds.
    burn_in : float
        Length of burn-in history to prepend.
    """

    if "t" not in data.columns or "side" not in data.columns:
        raise ValueError("data must contain 't' and 'side' columns")

    hist_mask = (data["t"] >= start - burn_in) & (data["t"] < start)
    win_mask = (data["t"] >= start) & (data["t"] <= end)

    buy_hist = data.loc[hist_mask & (data["side"] == "buy"), "t"].to_numpy()
    sell_hist = data.loc[hist_mask & (data["side"] == "sell"), "t"].to_numpy()
    buy = data.loc[win_mask & (data["side"] == "buy"), "t"].to_numpy()
    sell = data.loc[win_mask & (data["side"] == "sell"), "t"].to_numpy()

    _validate_monotone(buy_hist, "buy burn-in")
    _validate_monotone(sell_hist, "sell burn-in")
    _validate_monotone(buy, "buy window")
    _validate_monotone(sell, "sell window")

    return buy_hist, sell_hist, buy, sell


def _validate_monotone(arr: np.ndarray, label: str) -> None:
    if arr.size == 0:
        return
    if not np.all(arr[1:] >= arr[:-1]):
        raise ValueError(f"{label} timestamps must be non-decreasing")


def smmIter_windows(
    data: pd.DataFrame,
    cfg: SmmWindowConfig,
) -> Iterable[Tuple[int, float, float, Tuple[np.ndarray, ...]]]:
    """Yield window index, start, end, and associated event arrays."""

    smmStep = cfg.window_seconds * (1.0 - cfg.window_overlap)
    if smmStep <= 0:
        raise ValueError("window_overlap must be < 1.0")
    t_min = float(data["t"].min())
    t_max = float(data["t"].max())
    idx = 0
    start = t_min
    while start < t_max:
        end = start + cfg.window_seconds
        arrays = smmLoad_window(data, start, end, cfg.burn_in_seconds)
        yield idx, start, end, arrays
        idx += 1
        start += smmStep


__all__ = ["SmmWindowConfig", "smmLoad_config", "smmLoad_window", "smmIter_windows"]


