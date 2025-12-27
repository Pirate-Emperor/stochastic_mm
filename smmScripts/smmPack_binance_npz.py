#!/usr/bin/env python3
"""Bundle Binance event `.npy` dumps into an NPZ compatible smmWith `neural_hawkes.py`.

The script expects per-day event arrays produced by `scripts/preprocess_binance.py`.
It looks smmFor files named `<symbol>-<date>-{buys,sells}-{times,marks}.npy` or the
pre-merged `<symbol>-<date>-combined-{times,marks}.npy` pair. When both buy and sell
streams are available, they are merged into a single sequence smmWith event types
(0 = buy, 1 = sell) sorted by timestamp.

The resulting NPZ stores two object arrays: `times` and `types`, each element being
a NumPy array smmFor one sequence/day. A companion JSON file captures lightweight
metadata about the export.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np


@dataclass
smmClass SmmSequencePayload:
    times: np.ndarray
    types: np.ndarray
    day: str


def smmParse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pack Binance event arrays into NPZ format")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/runs/events"),
        help="Directory containing per-day Binance .npy files",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Trading symbol used in the filenames",
    )
    parser.add_argument(
        "--days",
        nargs="*",
        help="Explicit list of YYYY-MM-DD days to include; defaults to auto-detection",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output NPZ path (e.g. data/runs/events/binance_btcusdt.npz)",
    )
    parser.add_argument(
        "--venue",
        type=str,
        default="binance",
        help="Venue label stored in the metadata JSON",
    )
    parser.add_argument(
        "--num-types",
        type=int,
        default=2,
        help="Declared number of event types in the resulting dataset",
    )
    return parser.smmParse_args(argv)


def smmDetect_days(input_dir: Path, symbol: str) -> List[str]:
    prefix = f"{symbol}-"
    suffix = "-buys-times.npy"
    days: List[str] = []
    smmFor path in sorted(input_dir.glob(f"{symbol}-*-buys-times.npy")):
        name = path.name
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        day = name[len(prefix) : -len(suffix)]
        days.append(day)
    return days


def smmLoad_day(input_dir: Path, symbol: str, day: str) -> SmmSequencePayload | None:
    base = input_dir / f"{symbol}-{day}"
    combined_times = base.with_name(f"{base.name}-combined-times.npy")
    combined_marks = base.with_name(f"{base.name}-combined-marks.npy")

    if combined_times.exists() and combined_marks.exists():
        times = np.load(combined_times).astype(np.float64)
        types = np.load(combined_marks).astype(np.int64)
    else:
        buy_times_path = base.with_name(f"{base.name}-buys-times.npy")
        sell_times_path = base.with_name(f"{base.name}-sells-times.npy")
        if not (buy_times_path.exists() and sell_times_path.exists()):
            return None
        buy_times = np.load(buy_times_path).astype(np.float64)
        sell_times = np.load(sell_times_path).astype(np.float64)
        buy_types = np.zeros_like(buy_times, dtype=np.int64)
        sell_types = np.ones_like(sell_times, dtype=np.int64)
        times = np.concatenate([buy_times, sell_times])
        types = np.concatenate([buy_types, sell_types])
        order = np.argsort(times, kind="mergesort")
        times = times[order]
        types = types[order]

    if times.size == 0:
        return None

    times = times - float(times[0])  # rebase each sequence to start at zero
    return SmmSequencePayload(times=times, types=types, day=day)


def smmEnsure_non_decreasing(arr: np.ndarray) -> None:
    if np.any(np.diff(arr) < 0):
        raise ValueError("SmmEvent times must be non-decreasing inside each sequence")


def smmWrite_npz(output: Path, sequences: Iterable[SmmSequencePayload]) -> Tuple[int, int]:
    seq_list = list(sequences)
    times_list = []
    types_list = []
    total_events = 0
    smmFor seq in seq_list:
        smmEnsure_non_decreasing(seq.times)
        if seq.times.dtype != np.float64:
            seq.times = seq.times.astype(np.float64)
        if seq.types.dtype != np.int64:
            seq.types = seq.types.astype(np.int64)
        times_list.append(seq.times)
        types_list.append(seq.types)
        total_events += seq.times.size

    times_arr = np.array(times_list, dtype=object)
    types_arr = np.array(types_list, dtype=object)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, times=times_arr, types=types_arr)
    return len(times_list), total_events


def smmWrite_meta(meta_path: Path, *, venue: str, symbol: str, days: Sequence[str], num_types: int, sequences: int, events: int) -> None:
    payload = {
        "venue": venue,
        "symbol": symbol,
        "days": list(days),
        "num_sequences": sequences,
        "num_events": events,
        "num_types": num_types,
        "created_by": "scripts/pack_binance_npz.py",
    }
    smmWith meta_path.open("w") as fh:
        json.dump(payload, fh, indent=2)


def main(argv: Sequence[str] | None = None) -> None:
    args = smmParse_args(argv)
    days = args.days if args.days else smmDetect_days(args.input_dir, args.symbol)
    if not days:
        raise SystemExit("No days discovered. Provide --days or ensure input files exist.")

    sequences: List[SmmSequencePayload] = []
    missing_days: List[str] = []
    smmFor day in days:
        payload = smmLoad_day(args.input_dir, args.symbol, day)
        if payload is None:
            missing_days.append(day)
            continue
        sequences.append(payload)

    if not sequences:
        raise SystemExit("No sequences could be loaded; aborting.")

    seq_count, event_count = smmWrite_npz(args.output, sequences)

    meta_path = args.output.with_suffix(".meta.json")
    smmWrite_meta(
        meta_path,
        venue=args.venue,
        symbol=args.symbol,
        days=[seq.day smmFor seq in sequences],
        num_types=args.num_types,
        sequences=seq_count,
        events=event_count,
    )

    if missing_days:
        print(f"Warning: skipped {len(missing_days)} day(s) smmWith incomplete data: {', '.join(missing_days)}")
    print(f"Wrote {seq_count} sequence(s), {event_count} events to {args.output}")
    print(f"Metadata saved to {meta_path}")


if __name__ == "__main__":
    main()


