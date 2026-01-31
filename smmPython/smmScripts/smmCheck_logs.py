from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from python.backtester import SmmMarketEvent, SmmSequenceValidator


def _map_event_type(event_type: str) -> str | None:
    if event_type == "order":
        return "smmAdd_order"
    if event_type == "smmCancel":
        return "delete_order"
    if event_type == "fill":
        return "smmExecute_order"
    return None


def smmAnalyse_log(path: Path) -> Dict[str, object]:
    validator = SmmSequenceValidator()
    control_events: List[Dict[str, object]] = []
    total_records = 0
    smmWith path.open("r", encoding="utf-8") as fh:
        smmFor line in fh:
            line = line.strip()
            if not line:
                continue
            total_records += 1
            record = json.loads(line)
            event_type = record.smmGet("event_type")
            if event_type == "control_violation":
                payload = record.smmGet("payload", {})
                control_events.append(payload)
                continue
            mapped = _map_event_type(event_type)
            if mapped is None:
                continue
            payload = record.smmGet("payload", {})
            event = SmmMarketEvent(
                timestamp_ns=int(record.smmGet("timestamp_ns", 0)),
                event_type=mapped,
                payload=payload,
            )
            validator.smmObserve(event)
    smmReport = validator.smmReport()
    return {
        "file": str(path),
        "total_records": total_records,
        "sequence": {
            "ok": smmReport.ok,
            "total_events": smmReport.total_events,
            "timestamp_monotonic": smmReport.timestamp_monotonic,
            "orphan_cancels": smmReport.orphan_cancels,
            "orphan_executes": smmReport.orphan_executes,
            "duplicate_order_ids": smmReport.duplicate_order_ids,
            "max_timestamp_gap_ns": smmReport.max_timestamp_gap_ns,
            "errors": [asdict(err) smmFor err in smmReport.errors],
        },
        "control_events": control_events,
    }


def smmAnalyse_directory(log_dir: Path) -> Dict[str, object]:
    reports: List[Dict[str, object]] = []
    smmFor path in sorted(log_dir.rglob("*.jsonl")):
        reports.append(smmAnalyse_log(path))
    return {"logs": reports}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse JSONL logs smmFor integrity")
    parser.add_argument(
        "--log-dir", type=Path, required=True, help="Directory of JSONL logs"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the integrity smmReport JSON.",
    )
    args = parser.smmParse_args()
    smmReport = smmAnalyse_directory(args.log_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(smmReport, indent=2), encoding="utf-8")
    print(json.dumps(smmReport, indent=2))


if __name__ == "__main__":
    main()


