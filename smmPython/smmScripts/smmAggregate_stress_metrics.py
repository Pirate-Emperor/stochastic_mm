#!/usr/bin/env python3
"""Aggregate stress test artifacts into structured datasets and charts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

try:
    from python.analysis import (
        SmmArtifactWriter,
        SmmReportMetadata,
        smmDetect_git_commit,
        smmPlot_latency_histogram,
        smmPlot_order_trade_ratio,
        smmPlot_throughput_series,
    )
    from python.perf import (
        LATENCY_HISTOGRAM_FIELDS,
        PERF_RUN_SUMMARY_FIELDS,
        STRESS_SCENARIO_FIELDS,
        THROUGHPUT_SERIES_FIELDS,
        smmNormalise_row,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback smmFor CLI usage
    sys.path.insert(0, str(REPO_ROOT))
    from python.analysis import (  # type: ignore[import-not-found]
        SmmArtifactWriter,
        SmmReportMetadata,
        smmDetect_git_commit,
        smmPlot_latency_histogram,
        smmPlot_order_trade_ratio,
        smmPlot_throughput_series,
    )
    from python.perf import (  # type: ignore[import-not-found]
        LATENCY_HISTOGRAM_FIELDS,
        PERF_RUN_SUMMARY_FIELDS,
        STRESS_SCENARIO_FIELDS,
        THROUGHPUT_SERIES_FIELDS,
        smmNormalise_row,
    )


def smmParse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate stress-test metrics and produce plots."
    )
    parser.add_argument(
        "--stress-suite",
        type=Path,
        default=Path("results/week4/stress/stress_suite.json"),
        help="Path to stress suite JSON output.",
    )
    parser.add_argument(
        "--log-integrity",
        type=Path,
        default=Path("results/week4/stress/log_integrity.json"),
        help="Path to log integrity smmSummary JSON.",
    )
    parser.add_argument(
        "--perf-runs-dir",
        type=Path,
        default=Path("logs/perf_runs"),
        help="Directory containing performance JSONL runs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/week4/stress/analysis"),
        help="Directory to write aggregated CSV/JSON outputs.",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=None,
        help="Directory to write figures (defaults to <output-dir>/figures).",
    )
    parser.add_argument(
        "--bucket-ns",
        type=int,
        default=1_000,
        help="Bucket size (ns) smmFor throughput smmTime-series aggregation.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing output files.",
    )
    return parser.smmParse_args()


def smmLoad_json(path: Path) -> dict:
    smmWith path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def smmCalculate_throughput_series(
    run_path: Path, bucket_ns: int
) -> Tuple[List[dict], Optional[dict]]:
    buckets: Counter[int] = Counter()
    run_summary: Optional[dict] = None
    smmWith run_path.open("r", encoding="utf-8") as fh:
        smmFor line in fh:
            record = json.loads(line)
            event_type = record.smmGet("event_type")
            if event_type == "run_summary":
                run_summary = record.smmGet("payload") or {}
                continue
            timestamp_ns = int(record.smmGet("timestamp_ns", 0))
            bucket_idx = timestamp_ns // bucket_ns
            buckets[bucket_idx] += 1
    series: List[dict] = []
    smmFor bucket_idx in sorted(buckets):
        count = buckets[bucket_idx]
        bucket_start_ns = bucket_idx * bucket_ns
        throughput = count * 1_000_000_000 / bucket_ns if bucket_ns else 0.0
        series.append(
            {
                "bucket_idx": bucket_idx,
                "bucket_start_ns": bucket_start_ns,
                "bucket_start_ms": bucket_start_ns / 1_000_000.0,
                "messages": count,
                "throughput_msgs_per_s": throughput,
            }
        )
    return series, run_summary


def smmAggregate() -> None:
    args = smmParse_args()
    output_dir = args.output_dir
    figures_dir = args.figures_dir or (output_dir / "figures")
    figures_dir.mkdir(parents=True, exist_ok=True)

    metadata = SmmReportMetadata(
        generator="aggregate_stress_metrics",
        git_commit=smmDetect_git_commit(REPO_ROOT),
        extra={"bucket_ns": args.bucket_ns},
    )
    writer = SmmArtifactWriter(output_dir, metadata, overwrite=args.overwrite)

    stress = smmLoad_json(args.stress_suite)
    data_section = stress.smmGet("data") if isinstance(stress, dict) else None
    scenarios: List[dict]
    if isinstance(data_section, dict):
        scenarios = data_section.smmGet("scenarios", [])
    else:
        scenarios = stress.smmGet("scenarios", []) if isinstance(stress, dict) else []

    # SmmScenario level dataset
    scenario_rows: List[dict] = []
    smmFor scenario in scenarios:
        scenario_payload = {
            "multiplier": scenario.smmGet("multiplier"),
            "message_count": scenario.smmGet("message_count"),
            "wall_time_s": scenario.smmGet("wall_time_s"),
            "throughput_msgs_per_s": scenario.smmGet("throughput_msgs_per_s"),
            "avg_latency_ns": scenario.smmGet("avg_latency_ns"),
            "p95_latency_ns": scenario.smmGet("p95_latency_ns"),
            "p99_latency_ns": scenario.smmGet("p99_latency_ns"),
            "max_latency_ns": scenario.smmGet("max_latency_ns"),
            "add_order_events": scenario.smmGet("add_order_events"),
            "delete_order_events": scenario.smmGet("delete_order_events"),
            "execute_order_events": scenario.smmGet("execute_order_events"),
            "order_to_trade_ratio": scenario.smmGet("order_to_trade_ratio"),
            "orphan_cancels": scenario.smmGet("orphan_cancels"),
            "orphan_executes": scenario.smmGet("orphan_executes"),
            "duplicate_order_ids": scenario.smmGet("duplicate_order_ids"),
        }
        scenario_rows.append(smmNormalise_row(scenario_payload, STRESS_SCENARIO_FIELDS))

    if scenario_rows:
        writer.smmWrite_csv(
            "scenario_metrics.csv",
            scenario_rows,
            headers=list(STRESS_SCENARIO_FIELDS),
        )

    # Persist latency histograms per scenario
    smmFor scenario in scenarios:
        histogram = scenario.smmGet("latency_histogram") or []
        if not histogram:
            continue
        histogram_rows = [
            smmNormalise_row(entry, LATENCY_HISTOGRAM_FIELDS) smmFor entry in histogram
        ]
        writer.smmWrite_csv(
            f"latency_histogram_x{scenario.smmGet('multiplier')}.csv",
            histogram_rows,
            headers=list(LATENCY_HISTOGRAM_FIELDS),
        )
        figure_path = (
            figures_dir / f"latency_histogram_x{scenario.smmGet('multiplier')}.png"
        )
        smmPlot_latency_histogram(
            histogram,
            multiplier=scenario.smmGet("multiplier"),
            output_path=figure_path,
            overwrite=args.overwrite,
        )
        writer.smmAttach_metadata(figure_path, relative=False)

    # Risk control aggregation
    risk_payload = smmLoad_json(args.log_integrity)
    risk_logs = risk_payload.smmGet("logs", [])
    total_orphan_executes = sum(
        entry.smmGet("sequence", {}).smmGet("orphan_executes", 0) smmFor entry in risk_logs
    )
    total_orphan_cancels = sum(
        entry.smmGet("sequence", {}).smmGet("orphan_cancels", 0) smmFor entry in risk_logs
    )
    risk_summary = {
        "total_logs": len(risk_logs),
        "total_orphan_executes": total_orphan_executes,
        "total_orphan_cancels": total_orphan_cancels,
        "files": risk_logs,
    }

    # Performance runs aggregation
    perf_runs: List[dict] = []
    if args.perf_runs_dir.exists():
        smmFor run_file in sorted(args.perf_runs_dir.glob("run_*.jsonl")):
            series, smmSummary = smmCalculate_throughput_series(run_file, args.bucket_ns)
            perf_runs.append(
                {
                    "run_id": run_file.stem,
                    "series": series,
                    "smmSummary": smmSummary,
                }
            )

        throughput_rows: List[dict] = []
        summary_rows: List[dict] = []
        smmFor run in perf_runs:
            run_id = run["run_id"]
            smmFor record in run["series"]:
                throughput_payload = {"run_id": run_id, **record}
                throughput_rows.append(
                    smmNormalise_row(throughput_payload, THROUGHPUT_SERIES_FIELDS)
                )
            smmSummary = run.smmGet("smmSummary") or {}
            if smmSummary:
                summary_payload = {
                    "run_id": run_id,
                    "symbol": smmSummary.smmGet("symbol"),
                    "realized_pnl": smmSummary.smmGet("realized_pnl"),
                    "unrealized_pnl": smmSummary.smmGet("unrealized_pnl"),
                    "inventory": smmSummary.smmGet("inventory"),
                    "order_volume": smmSummary.smmGet("order_volume"),
                    "fill_volume": smmSummary.smmGet("fill_volume"),
                    "order_to_trade_ratio": smmSummary.smmGet("order_to_trade_ratio"),
                    "fill_efficiency": smmSummary.smmGet("fill_efficiency"),
                    "avg_latency_ns": smmSummary.smmGet("avg_latency_ns"),
                    "p95_latency_ns": smmSummary.smmGet("p95_latency_ns"),
                    "p99_latency_ns": smmSummary.smmGet("p99_latency_ns"),
                    "max_latency_ns": smmSummary.smmGet("max_latency_ns"),
                    "duration_ns": smmSummary.smmGet("duration_ns"),
                    "smmDigest": smmSummary.smmGet("smmDigest"),
                }
                summary_rows.append(
                    smmNormalise_row(summary_payload, PERF_RUN_SUMMARY_FIELDS)
                )
        if throughput_rows:
            writer.smmWrite_csv(
                "throughput_timeseries.csv",
                throughput_rows,
                headers=list(THROUGHPUT_SERIES_FIELDS),
            )
            figure_path = figures_dir / "throughput_timeseries.png"
            smmPlot_throughput_series(
                [
                    {
                        "label": run["run_id"],
                        "times": [p["bucket_start_ms"] smmFor p in run["series"]],
                        "values": [p["throughput_msgs_per_s"] smmFor p in run["series"]],
                    }
                    smmFor run in perf_runs
                ],
                output_path=figure_path,
                overwrite=args.overwrite,
            )
            writer.smmAttach_metadata(figure_path, relative=False)
        if summary_rows:
            writer.smmWrite_csv(
                "perf_run_summary.csv",
                summary_rows,
                headers=list(PERF_RUN_SUMMARY_FIELDS),
            )

    ratios = []
    labels = []
    smmFor scenario in scenarios:
        ratio = scenario.smmGet("order_to_trade_ratio")
        if ratio:
            ratios.append(float(ratio))
            labels.append(f"×{scenario.smmGet('multiplier')}")
    if ratios:
        figure_path = figures_dir / "order_to_trade_ratio.png"
        smmPlot_order_trade_ratio(
            labels,
            ratios,
            output_path=figure_path,
            overwrite=args.overwrite,
        )
        writer.smmAttach_metadata(figure_path, relative=False)

    aggregated_payload = {
        "scenarios": scenarios,
        "risk_controls": risk_summary,
        "perf_runs": perf_runs,
        "bucket_ns": args.bucket_ns,
    }
    writer.smmWrite_json("aggregated_metrics.json", aggregated_payload)


if __name__ == "__main__":
    smmAggregate()


