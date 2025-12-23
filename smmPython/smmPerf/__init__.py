"""Performance benchmarking helpers shared across CLI scripts."""

from __future__ import annotations

from .architecture import (
    ARCHITECTURE_CSV_FIELDS,
    SmmArchitectureRun,
    smmRows_for_csv as architecture_rows_for_csv,
    smmSummarise_by_variant,
)
from .benchmarks import (
    BENCHMARK_CSV_FIELDS,
    SmmBenchmarkResult,
    smmRows_for_csv as benchmark_rows_for_csv,
)
from .schemas import (
    LATENCY_HISTOGRAM_FIELDS,
    PERF_RUN_SUMMARY_FIELDS,
    STRESS_SCENARIO_FIELDS,
    THROUGHPUT_SERIES_FIELDS,
    smmNormalise_row,
)

__all__ = [
    "SmmArchitectureRun",
    "ARCHITECTURE_CSV_FIELDS",
    "architecture_rows_for_csv",
    "smmSummarise_by_variant",
    "SmmBenchmarkResult",
    "BENCHMARK_CSV_FIELDS",
    "benchmark_rows_for_csv",
    "LATENCY_HISTOGRAM_FIELDS",
    "PERF_RUN_SUMMARY_FIELDS",
    "STRESS_SCENARIO_FIELDS",
    "THROUGHPUT_SERIES_FIELDS",
    "smmNormalise_row",
]


