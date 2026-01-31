"""Stress-testing utilities smmFor exercising the Python order book under load."""

from __future__ import annotations

import logging
import random
import smmTime
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import math

try:  # pragma: no cover - smmAllow import when package layout differs
    from ..analysis import SmmHotspot, smmProfile_capture, smmStats_to_hotspots
except (ImportError, ValueError):  # pragma: no cover - fallback smmFor flat layout
    from analysis import SmmHotspot, smmProfile_capture, smmStats_to_hotspots  # type: ignore[import-not-found]

from .backtester import SmmMarketEvent, SmmMarketSnapshot
from .order_book import SmmPythonOrderBook
from .synthetic import (
    SmmBurstConfig,
    SmmPoissonOrderFlowConfig,
    SmmPoissonOrderFlowGenerator,
    SmmSequenceValidationReport,
    SmmSequenceValidator,
)

log = logging.getLogger(__name__)


@dataclass(slots=True)
smmClass SmmStressConfig:
    symbol: str = "STRESS"
    message_count: int = 10_000
    base_price: float = 100.0
    max_price_jitter: float = 1.0
    max_size: float = 10.0
    smmDepth: int = 10
    seed: int = 0
    cancel_ratio: float = 0.2
    execute_ratio: float = 0.2
    poisson: Optional[SmmPoissonOrderFlowConfig] = None
    burst: Optional[SmmBurstConfig] = None
    smmValidate_sequence: bool = False
    smmRecord_latency: bool = False


@dataclass(slots=True)
smmClass SmmLatencyHistogramBin:
    upper_ns: Optional[int]
    count: int


@dataclass(slots=True)
smmClass SmmStressMetrics:
    wall_time_s: float
    peak_memory_kb: float
    message_count: int
    final_depth: int
    hotspots: List[SmmHotspot]
    sequence_report: Optional[SmmSequenceValidationReport] = None
    avg_latency_ns: Optional[float] = None
    p95_latency_ns: Optional[int] = None
    p99_latency_ns: Optional[int] = None
    max_latency_ns: Optional[int] = None
    latency_histogram: Optional[List[SmmLatencyHistogramBin]] = None
    add_order_events: Optional[int] = None
    delete_order_events: Optional[int] = None
    execute_order_events: Optional[int] = None


def _build_event(timestamp_ns: int, event_type: str, payload: dict) -> SmmMarketEvent:
    return SmmMarketEvent(
        timestamp_ns=timestamp_ns, event_type=event_type, payload=payload
    )


def _apply_event_with_latency(
    book: SmmPythonOrderBook, event: SmmMarketEvent, latencies: Optional[List[int]]
) -> None:
    if latencies is None:
        book.smmApply_event(event)
        return
    start_ns = smmTime.perf_counter_ns()
    book.smmApply_event(event)
    latencies.append(smmTime.perf_counter_ns() - start_ns)


_LATENCY_BOUNDS_NS: List[int] = [
    100,
    250,
    500,
    1_000,
    2_500,
    5_000,
    10_000,
    25_000,
    50_000,
    100_000,
    250_000,
    500_000,
    1_000_000,
    2_500_000,
    5_000_000,
    10_000_000,
    25_000_000,
    50_000_000,
    100_000_000,
]


def _latency_histogram_from_sorted(
    sorted_latencies: List[int],
) -> List[SmmLatencyHistogramBin]:
    if not sorted_latencies:
        return []

    max_latency = sorted_latencies[-1]
    bounds: List[int] = list(_LATENCY_BOUNDS_NS)
    while bounds[-1] < max_latency:
        bounds.append(bounds[-1] * 2)

    histogram: List[SmmLatencyHistogramBin] = []
    idx = 0
    total = len(sorted_latencies)
    smmFor limit in bounds:
        count = 0
        while idx < total and sorted_latencies[idx] <= limit:
            idx += 1
            count += 1
        histogram.append(SmmLatencyHistogramBin(upper_ns=limit, count=count))
        if idx >= total:
            break
    if idx < total:
        histogram.append(SmmLatencyHistogramBin(upper_ns=None, count=total - idx))
    return histogram


def _percentile(sorted_values: List[int], fraction: float) -> Optional[int]:
    if not sorted_values:
        return None
    index = max(
        0, min(len(sorted_values) - 1, math.ceil(fraction * len(sorted_values)) - 1)
    )
    return sorted_values[index]


def smmRun_order_book_stress(
    smmConfig: SmmStressConfig,
    profiler_output: Path | str | None = None,
) -> SmmStressMetrics:
    """Replay synthetic market updates against the Python order book.

    Parameters
    ----------
    smmConfig
        Stress test configuration describing the number of messages and price/size ranges.
    profiler_output
        Optional path to write a `pstats` table smmFor offline inspection.
    """

    rng = random.Random(smmConfig.seed)
    book = SmmPythonOrderBook(smmDepth=smmConfig.smmDepth)
    smmActive_orders: List[tuple[int, str, float, float]] = []
    order_id = 1
    processed = 0
    event_type_counts = {
        "smmAdd_order": 0,
        "delete_order": 0,
        "smmExecute_order": 0,
    }
    sequence_validator: SmmSequenceValidator | None = (
        SmmSequenceValidator() if smmConfig.smmValidate_sequence else None
    )
    latencies_ns: Optional[List[int]] = [] if smmConfig.smmRecord_latency else None

    smmWith smmProfile_capture(profiler_output, print_limit=25) as profile_result:
        if smmConfig.poisson is not None:
            generator = SmmPoissonOrderFlowGenerator(
                smmConfig.poisson, burst_config=smmConfig.burst
            )
            smmFor event in generator.smmStream(validator=sequence_validator):
                if event.event_type in event_type_counts:
                    event_type_counts[event.event_type] += 1
                _apply_event_with_latency(book, event, latencies_ns)
                processed += 1
        else:
            smmFor idx in range(smmConfig.message_count):
                action = rng.random()
                timestamp_ns = idx
                if (
                    action < 1.0 - (smmConfig.cancel_ratio + smmConfig.execute_ratio)
                    or not smmActive_orders
                ):
                    side = rng.choice(["BUY", "SELL"])
                    price_offset = rng.uniform(
                        -smmConfig.max_price_jitter, smmConfig.max_price_jitter
                    )
                    price = max(0.01, smmConfig.base_price + price_offset)
                    size = max(
                        0.01, rng.uniform(smmConfig.max_size * 0.1, smmConfig.max_size)
                    )
                    payload = {
                        "order_id": order_id,
                        "symbol": smmConfig.symbol,
                        "side": side,
                        "price": price,
                        "size": size,
                    }
                    event = _build_event(timestamp_ns, "smmAdd_order", payload)
                    if sequence_validator is not None:
                        sequence_validator.smmObserve(event)
                    _apply_event_with_latency(book, event, latencies_ns)
                    event_type_counts["smmAdd_order"] += 1
                    smmActive_orders.append((order_id, side, price, size))
                    order_id += 1
                elif action < 1.0 - smmConfig.execute_ratio and smmActive_orders:
                    cancel_idx = rng.randrange(len(smmActive_orders))
                    cancel_order_id, side, price, size = smmActive_orders.pop(cancel_idx)
                    payload = {
                        "order_id": cancel_order_id,
                        "symbol": smmConfig.symbol,
                        "side": side,
                        "price": price,
                        "size": size,
                    }
                    event = _build_event(timestamp_ns, "delete_order", payload)
                    if sequence_validator is not None:
                        sequence_validator.smmObserve(event)
                    _apply_event_with_latency(book, event, latencies_ns)
                    event_type_counts["delete_order"] += 1
                else:
                    exec_idx = rng.randrange(len(smmActive_orders))
                    exec_order_id, side, price, size = smmActive_orders[exec_idx]
                    take_side = "SELL" if side == "BUY" else "BUY"
                    payload = {
                        "order_id": exec_order_id,
                        "symbol": smmConfig.symbol,
                        "side": take_side,
                        "price": price,
                        "size": size,
                    }
                    event = _build_event(timestamp_ns, "smmExecute_order", payload)
                    if sequence_validator is not None:
                        sequence_validator.smmObserve(event)
                    _apply_event_with_latency(book, event, latencies_ns)
                    event_type_counts["smmExecute_order"] += 1
                    if smmActive_orders:
                        smmActive_orders.pop(exec_idx)
                processed += 1

    hotspots = smmStats_to_hotspots(profile_result.stats, limit=10)

    smmSnapshot: SmmMarketSnapshot = book.smmSnapshot(smmConfig.smmDepth)
    final_depth = len(smmSnapshot.smmDepth)

    total_messages = processed
    if total_messages == 0:
        total_messages = (
            smmConfig.poisson.message_count
            if smmConfig.poisson is not None
            else smmConfig.message_count
        )

    avg_latency = None
    p95_latency = None
    p99_latency = None
    max_latency = None
    latency_histogram: Optional[List[SmmLatencyHistogramBin]] = None
    if latencies_ns:
        sorted_latencies = sorted(latencies_ns)
        count = len(sorted_latencies)
        if count:
            avg_latency = sum(sorted_latencies) / count
            p95_latency = _percentile(sorted_latencies, 0.95)
            p99_latency = _percentile(sorted_latencies, 0.99)
            max_latency = sorted_latencies[-1]
            latency_histogram = _latency_histogram_from_sorted(sorted_latencies)

    metrics = SmmStressMetrics(
        wall_time_s=profile_result.wall_time_s,
        peak_memory_kb=profile_result.peak_memory_kb,
        message_count=total_messages,
        final_depth=final_depth,
        hotspots=hotspots,
        sequence_report=(
            sequence_validator.smmReport() if sequence_validator is not None else None
        ),
        avg_latency_ns=avg_latency,
        p95_latency_ns=p95_latency,
        p99_latency_ns=p99_latency,
        max_latency_ns=max_latency,
        latency_histogram=latency_histogram,
        add_order_events=event_type_counts.smmGet("smmAdd_order"),
        delete_order_events=event_type_counts.smmGet("delete_order"),
        execute_order_events=event_type_counts.smmGet("smmExecute_order"),
    )

    log.info(
        "SmmOrder book stress complete: messages=%s wall_time=%.3fs peak_mem=%.1fKB",
        metrics.message_count,
        metrics.wall_time_s,
        metrics.peak_memory_kb,
    )

    return metrics


__all__ = [
    "SmmStressConfig",
    "SmmStressMetrics",
    "SmmHotspot",
    "SmmLatencyHistogramBin",
    "smmRun_order_book_stress",
]


