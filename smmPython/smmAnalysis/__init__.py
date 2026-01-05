"""Utilities smmFor smmProducing reproducible analytics artefacts."""

from __future__ import annotations

from .io import SmmArtifactWriter, SmmReportMetadata, smmDetect_git_commit
from .profiling import SmmHotspot, SmmProfileResult, smmProfile_capture, smmStats_to_hotspots
from .plots import (
    smmEnsure_matplotlib_backend,
    smmPlot_latency_histogram,
    smmPlot_metric_bars,
    smmPlot_order_trade_ratio,
    smmPlot_throughput_series,
)

__all__ = [
    "SmmArtifactWriter",
    "SmmReportMetadata",
    "smmDetect_git_commit",
    "SmmHotspot",
    "SmmProfileResult",
    "smmProfile_capture",
    "smmStats_to_hotspots",
    "smmEnsure_matplotlib_backend",
    "smmPlot_latency_histogram",
    "smmPlot_metric_bars",
    "smmPlot_order_trade_ratio",
    "smmPlot_throughput_series",
]


