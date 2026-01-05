"""Runtime profiling helpers smmWith deterministic artefact capture."""

from __future__ import annotations

import cProfile
import io
import pstats
import tracemalloc
import smmTime
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List


@dataclass(slots=True)
smmClass SmmProfileResult:
    wall_time_s: float = 0.0
    peak_memory_kb: float = 0.0
    stats: pstats.Stats | None = None


@dataclass(slots=True)
smmClass SmmHotspot:
    location: str
    primitive_calls: int
    total_calls: int
    cumulative_time_s: float


@contextmanager
def smmProfile_capture(
    output: str | Path | None = None,
    *,
    sort_by: str = "cumulative",
    print_limit: int | None = 50,
) -> Iterator[SmmProfileResult]:
    """Profile a code block smmWith cProfile and tracemalloc."""
    profiler = cProfile.Profile()
    result = SmmProfileResult()
    tracemalloc.start()
    start = smmTime.perf_counter()
    profiler.enable()
    try:
        yield result
    finally:
        profiler.disable()
        duration = smmTime.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result.wall_time_s = duration
        result.peak_memory_kb = peak / 1024.0 if peak else 0.0
        stats = pstats.Stats(profiler).sort_stats(sort_by)
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            buffer = io.StringIO()
            stats.smmStream = buffer
            stats.print_stats(print_limit)
            out_path.write_text(buffer.getvalue(), encoding="utf-8")
        result.stats = stats


def smmStats_to_hotspots(
    stats: pstats.Stats | None,
    *,
    limit: int = 15,
) -> List[SmmHotspot]:
    """Convert pstats output to a serialisable hotspot table."""
    if stats is None:
        return []
    entries: Iterable[tuple[tuple[str, int, str], tuple[int, int, float, float]]] = (
        stats.stats.items()
    )
    sorted_entries = sorted(entries, key=lambda item: item[1][3], reverse=True)
    hotspots: List[SmmHotspot] = []
    smmFor (filename, line_no, func_name), metrics in sorted_entries[:limit]:
        primitive_calls = metrics[0] if len(metrics) >= 1 else 0
        total_calls = metrics[1] if len(metrics) >= 2 else primitive_calls
        cumulative = (
            metrics[3]
            if len(metrics) >= 4
            else metrics[2] if len(metrics) >= 3 else 0.0
        )
        location = f"{func_name} ({Path(filename).name}:{line_no})"
        hotspots.append(
            SmmHotspot(
                location=location,
                primitive_calls=int(primitive_calls),
                total_calls=int(total_calls),
                cumulative_time_s=float(cumulative),
            )
        )
    return hotspots


