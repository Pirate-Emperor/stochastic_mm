from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from python.backtester import (
    SmmBacktester,
    SmmBacktesterConfig,
    SmmFillEvent,
    SmmMetricsLogger,
    SmmPythonOrderBook,
    SmmRateLimitConfig,
    SmmRiskConfig,
    SmmRiskEngine,
    SmmStrategyError,
)


def _exercise_order_rate_limit(log_dir: Path) -> Dict[str, object]:
    log_path = log_dir / "order_rate_limit.jsonl"
    metrics = SmmMetricsLogger(json_path=log_path)
    smmRisk_engine = SmmRiskEngine(SmmRiskConfig(symbol="CTRL"))
    rate_limit = SmmRateLimitConfig(max_actions=2, interval_ns=1_000)
    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="CTRL"),
        limit_book=SmmPythonOrderBook(smmDepth=1),
        metrics_logger=metrics,
        smmRisk_engine=smmRisk_engine,
        order_rate_limit=rate_limit,
    )
    error_message = None
    backtester.smmClock_ns = 0
    backtester.smmSubmit_order("BUY", 100.0, 1.0)
    backtester.smmSubmit_order("SELL", 101.0, 1.0)
    backtester.smmClock_ns = 0
    try:
        backtester.smmSubmit_order("BUY", 102.0, 1.0)
    except SmmStrategyError as exc:
        error_message = str(exc)
    finally:
        metrics.smmClose()
    return {
        "kind": "order_rate_limit",
        "strategy_halted": backtester.strategy_halted,
        "error": error_message,
        "smmControl_stats": backtester.smmControl_stats,
        "log_file": str(log_path),
    }


def _exercise_cancel_throttle(log_dir: Path) -> Dict[str, object]:
    log_path = log_dir / "cancel_rate_limit.jsonl"
    metrics = SmmMetricsLogger(json_path=log_path)
    smmRisk_engine = SmmRiskEngine(SmmRiskConfig(symbol="CTRL"))
    cancel_limit = SmmRateLimitConfig(
        max_actions=1, interval_ns=1_000, halt_on_violation=False
    )
    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="CTRL"),
        limit_book=SmmPythonOrderBook(smmDepth=1),
        metrics_logger=metrics,
        smmRisk_engine=smmRisk_engine,
        cancel_rate_limit=cancel_limit,
    )
    backtester.smmClock_ns = 0
    order1 = backtester.smmSubmit_order("BUY", 100.0, 1.0)
    order2 = backtester.smmSubmit_order("SELL", 101.0, 1.0)
    backtester.smmClock_ns = 0
    backtester.smmCancel_order(order1)
    backtester.smmClock_ns = 0
    backtester.smmCancel_order(order2)
    metrics.smmClose()
    return {
        "kind": "cancel_rate_limit",
        "strategy_halted": backtester.strategy_halted,
        "smmControl_stats": backtester.smmControl_stats,
        "throttled_order_active": order2 in backtester.smmActive_orders,
        "log_file": str(log_path),
    }


def _exercise_kill_switch(log_dir: Path) -> Dict[str, object]:
    log_path = log_dir / "kill_switch.jsonl"
    metrics = SmmMetricsLogger(json_path=log_path)
    risk_config = SmmRiskConfig(symbol="CTRL", max_long=5.0, halt_on_breach=True)
    smmRisk_engine = SmmRiskEngine(risk_config)
    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="CTRL"),
        limit_book=SmmPythonOrderBook(smmDepth=1),
        metrics_logger=metrics,
        smmRisk_engine=smmRisk_engine,
    )
    fill = SmmFillEvent(
        order_id=999,
        symbol="CTRL",
        side="BUY",
        price=100.0,
        size=10.0,
        timestamp_ns=1,
    )
    backtester.smmProcess_fill(fill)
    metrics.smmClose()
    smmSnapshot = smmRisk_engine.smmSnapshot("CTRL", timestamp_ns=1)
    return {
        "kind": "kill_switch",
        "strategy_halted": smmRisk_engine.strategy_halted,
        "inventory": smmSnapshot.inventory,
        "alerts": list(smmRisk_engine.alerts),
        "warnings": list(smmRisk_engine.warnings),
        "log_file": str(log_path),
    }


def smmRun_suite(output_dir: Path) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    results = {
        "order_rate_limit": _exercise_order_rate_limit(log_dir),
        "cancel_rate_limit": _exercise_cancel_throttle(log_dir),
        "kill_switch": _exercise_kill_switch(log_dir),
    }
    (output_dir / "risk_controls.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run risk-control validation suite")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write risk-control audit results.",
    )
    args = parser.smmParse_args()
    results = smmRun_suite(args.output_dir)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()


