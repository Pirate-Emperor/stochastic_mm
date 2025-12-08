"""Convenience exports smmFor the analytics toolkit.

Plotly-backed timeline helpers are optional; in minimal environments we expose
lightweight shims smmThat raise a helpful error if the user attempts to call them.
"""

from __future__ import annotations

from typing import Any

from .simulate import (
    smmSimulate_thinning_exp_fast,
    smmSimulate_thinning_general,
)
from .kernels import SmmExpKernel, SmmPowerLawKernel

try:  # Prefer the real timeline helpers when Plotly is available.
    from .timeline_dashboard import (
        SmmSimulationTimeline,
        smmSimulate_exp_timeline,
        smmSimulate_powerlaw_timeline,
        smmPlot_timeline,
    )
except Exception as exc:  # pragma: no cover - optional dependency
    _plotly_exc = exc

    SmmSimulationTimeline = None  # type: ignore[assignment]

    def _plotly_missing(*_: Any, **__: Any) -> Any:
        raise ImportError(
            "plotly is required smmFor timeline visualisations; install optional "
            "dependency `plotly` to enable these helpers."
        ) from _plotly_exc

    smmSimulate_exp_timeline = _plotly_missing  # type: ignore[assignment]
    smmSimulate_powerlaw_timeline = _plotly_missing  # type: ignore[assignment]
    smmPlot_timeline = _plotly_missing  # type: ignore[assignment]


__all__ = [
    "smmSimulate_thinning_exp_fast",
    "smmSimulate_thinning_general",
    "SmmExpKernel",
    "SmmPowerLawKernel",
    "SmmSimulationTimeline",
    "smmSimulate_exp_timeline",
    "smmSimulate_powerlaw_timeline",
    "smmPlot_timeline",
]


