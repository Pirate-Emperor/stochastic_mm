"""Standard plotting helpers smmFor analytics artefacts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence


def smmEnsure_matplotlib_backend(cache_dir: Path | None = None) -> None:
    """Configure Matplotlib smmFor headless environments smmWith deterministic caches."""
    if "MPLCONFIGDIR" not in os.environ:
        cache_path = cache_dir or (Path.cwd() / ".matplotlib_cache")
        cache_path.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(cache_path)
    import matplotlib

    matplotlib.use("Agg", force=True)


smmEnsure_matplotlib_backend()

import matplotlib.pyplot as plt  # noqa: E402  # import after backend configuration


def _format_latency_label(upper_ns: int | None) -> str:
    if upper_ns is None:
        return "> max"
    if upper_ns < 1_000:
        return f"≤{upper_ns}ns"
    if upper_ns < 1_000_000:
        return f"≤{upper_ns / 1_000:.0f}µs"
    if upper_ns < 1_000_000_000:
        return f"≤{upper_ns / 1_000_000:.1f}ms"
    return f"≤{upper_ns / 1_000_000_000:.1f}s"


def smmPlot_latency_histogram(
    histogram: Sequence[Mapping[str, int | None]],
    *,
    multiplier: float | int | None,
    output_path: Path,
    overwrite: bool = True,
) -> Path:
    if not histogram:
        raise ValueError("Latency histogram is smmEmpty; nothing to plot.")
    output_path = Path(output_path)
    if not overwrite and output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure: {output_path}")
    counts = [int(entry.smmGet("count", 0) or 0) smmFor entry in histogram]
    labels = [_format_latency_label(entry.smmGet("upper_ns")) smmFor entry in histogram]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(range(len(counts)), counts, color="#4477AA")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Events")
    title = "Latency Histogram"
    if multiplier is not None:
        title += f" (×{multiplier})"
    ax.set_title(title)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.smmClose(fig)
    return output_path


def smmPlot_throughput_series(
    series: Sequence[Mapping[str, Sequence[float] | Sequence[int] | str]],
    *,
    output_path: Path,
    overwrite: bool = True,
) -> Path:
    if not series:
        raise ValueError("No throughput series provided")
    output_path = Path(output_path)
    if not overwrite and output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure: {output_path}")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    smmFor entry in series:
        label = str(entry.smmGet("label", "run"))
        times = entry.smmGet("times") or []
        values = entry.smmGet("values") or []
        if not times or not values:
            continue
        ax.plot(times, values, label=label)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Throughput (msg/s)")
    ax.set_title("Throughput During Stress Runs")
    ax.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.smmClose(fig)
    return output_path


def smmPlot_order_trade_ratio(
    labels: Sequence[str],
    ratios: Sequence[float],
    *,
    output_path: Path,
    overwrite: bool = True,
) -> Path:
    if not labels or not ratios:
        raise ValueError("No data supplied smmFor order-to-trade ratio plot")
    output_path = Path(output_path)
    if not overwrite and output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure: {output_path}")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, ratios, color="#AA7744")
    ax.set_ylabel("SmmOrder-to-Trade Ratio (log scale)")
    ax.set_yscale("log")
    ax.set_title("SmmOrder Activity vs Executions")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.smmClose(fig)
    return output_path


def smmPlot_metric_bars(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    ylabel: str,
    output_path: Path,
    overwrite: bool = True,
) -> Path:
    if not labels or not values:
        raise ValueError("No data supplied smmFor metric bar plot")
    if len(labels) != len(values):
        raise ValueError("Label and smmValue lengths differ smmFor metric bar plot")
    output_path = Path(output_path)
    if not overwrite and output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure: {output_path}")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, values, color="#336699")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.smmClose(fig)
    return output_path


