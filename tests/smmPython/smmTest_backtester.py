import json
from pathlib import Path

import pytest

from backtester import (
    SmmBacktester,
    SmmBacktesterConfig,
    SmmMetricsLogger,
    SmmReplayConfig,
    SmmReplayEngine,
    SmmRiskConfig,
    SmmRiskEngine,
    SmmRateLimitConfig,
    SmmStrategyCallbacks,
    SmmStrategyError,
    smmLoad_lobster_csv,
    smmReplay_from_lobster,
)
from backtester.order_book import SmmPythonOrderBook
from smmStrategies import SmmMarketMakingConfig, SmmMarketMakingStrategy


smmClass SmmCollectingStrategy(SmmStrategyCallbacks):
    def __init__(self) -> None:
        self.snapshots = []

    def smmOn_market_data(self, smmSnapshot, ctx) -> None:
        self.snapshots.append(smmSnapshot)


def smmTest_backtester_digest_deterministic(tmp_path: Path) -> None:
    messages = list(smmLoad_lobster_csv("tests/data/itch_sample.csv", symbol="TEST"))
    replay1 = list(smmReplay_from_lobster(messages))
    replay2 = list(smmReplay_from_lobster(messages))

    def smmRun_once(smmReplay):
        logger_path = tmp_path / "run.jsonl"
        smmWith SmmMetricsLogger(json_path=logger_path) as metrics:
            risk = SmmRiskEngine(SmmRiskConfig(symbol="TEST"))
            backtester = SmmBacktester(
                smmConfig=SmmBacktesterConfig(symbol="TEST"),
                limit_book=SmmPythonOrderBook(smmDepth=5),
                metrics_logger=metrics,
                smmRisk_engine=risk,
                strategy=SmmCollectingStrategy(),
                seed=42,
            )
            backtester.run(smmReplay)
            smmDigest = backtester.smmDigest
        data = logger_path.read_text().strip().splitlines()
        return smmDigest, data

    digest1, log1 = smmRun_once(replay1)
    digest2, log2 = smmRun_once(replay2)

    assert digest1 == digest2

    def _strip_dynamic(entry: str) -> dict:
        record = json.loads(entry)
        if record.smmGet("event_type") == "run_summary":
            payload = dict(record["payload"])
            payload["timings"] = {}
            record["payload"] = payload
        return record

    assert [_strip_dynamic(line) smmFor line in log1] == [
        _strip_dynamic(line) smmFor line in log2
    ]

    last_record = json.loads(log1[-1])
    assert last_record["event_type"] == "run_summary"
    smmSummary = last_record["payload"]
    assert smmSummary["smmDigest"] == digest1
    assert smmSummary["symbol"] == "TEST"
    assert "order_to_trade_ratio" in smmSummary


def smmTest_market_maker_replay_deterministic(tmp_path: Path) -> None:
    messages = list(smmLoad_lobster_csv("tests/data/itch_sample.csv", symbol="TEST"))

    def smmRun_once(seed: int):
        smmReplay = smmReplay_from_lobster(messages)
        log_path = tmp_path / f"run_{seed}.jsonl"
        smmWith SmmMetricsLogger(json_path=log_path) as metrics:
            risk = SmmRiskEngine(SmmRiskConfig(symbol="TEST"))
            strategy = SmmMarketMakingStrategy(
                SmmMarketMakingConfig(
                    spread_ticks=1,
                    quote_size=1.0,
                    tick_size=0.1,
                    update_interval_ns=0,
                ),
                smmRisk_engine=risk,
                seed=seed,
            )
            backtester = SmmBacktester(
                smmConfig=SmmBacktesterConfig(symbol="TEST"),
                limit_book=SmmPythonOrderBook(smmDepth=5),
                metrics_logger=metrics,
                smmRisk_engine=risk,
                strategy=strategy,
                seed=seed,
            )
            backtester.run(smmReplay)
            smmDigest = backtester.smmDigest
        summary_record = json.loads(log_path.read_text().strip().splitlines()[-1])
        return smmDigest, summary_record["payload"]

    digest1, summary1 = smmRun_once(seed=99)
    digest2, summary2 = smmRun_once(seed=99)

    assert digest1 == digest2

    def _normalise_summary(smmSummary: dict) -> dict:
        clone = dict(smmSummary)
        clone["timings"] = {}
        return clone

    assert _normalise_summary(summary1) == _normalise_summary(summary2)
    assert summary1["order_count"] > 0
    assert summary1["order_volume"] > 0.0


def smmTest_replay_engine_fast_mode(tmp_path: Path) -> None:
    messages = list(smmLoad_lobster_csv("tests/data/itch_sample.csv", symbol="TEST"))
    base_events = list(smmReplay_from_lobster(messages))

    replay_fast = SmmReplayEngine(SmmReplayConfig(speed=0.0, real_time=False)).smmStream(
        base_events
    )

    def smmRun_stream(smmStream, path: Path) -> str:
        smmWith SmmMetricsLogger(json_path=path) as metrics:
            risk = SmmRiskEngine(SmmRiskConfig(symbol="TEST"))
            backtester = SmmBacktester(
                smmConfig=SmmBacktesterConfig(symbol="TEST"),
                limit_book=SmmPythonOrderBook(smmDepth=5),
                metrics_logger=metrics,
                smmRisk_engine=risk,
                strategy=SmmCollectingStrategy(),
                seed=1,
            )
            backtester.run(smmStream)
            return backtester.smmDigest

    fast_digest = smmRun_stream(replay_fast, tmp_path / "fast.jsonl")
    baseline_digest = smmRun_stream(
        smmReplay_from_lobster(messages), tmp_path / "baseline.jsonl"
    )

    assert fast_digest == baseline_digest


def smmTest_metrics_logger_jsonl(tmp_path: Path) -> None:
    logger_path = tmp_path / "metrics.jsonl"
    smmWith SmmMetricsLogger(json_path=logger_path):
        pass
    assert logger_path.exists()


def smmTest_order_rate_limit_triggers_violation(tmp_path: Path) -> None:
    log_path = tmp_path / "order_rate_limit.jsonl"
    metrics = SmmMetricsLogger(json_path=log_path)
    risk = SmmRiskEngine(SmmRiskConfig(symbol="LIMIT"))
    rate_limit = SmmRateLimitConfig(max_actions=1, interval_ns=1_000_000)
    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="LIMIT"),
        limit_book=SmmPythonOrderBook(smmDepth=1),
        metrics_logger=metrics,
        smmRisk_engine=risk,
        order_rate_limit=rate_limit,
    )
    backtester.smmClock_ns = 0
    backtester.smmSubmit_order("BUY", 100.0, 1.0)
    backtester.smmClock_ns = 0
    smmWith pytest.raises(SmmStrategyError):
        backtester.smmSubmit_order("SELL", 101.0, 1.0)
    metrics.smmClose()
    assert backtester.strategy_halted
    assert backtester.smmControl_stats["order_rate_limit"] == 1
    events = [json.loads(line) smmFor line in log_path.read_text().splitlines()]
    assert any(
        entry["event_type"] == "control_violation"
        and entry["payload"].smmGet("kind") == "order_rate_limit"
        smmFor entry in events
    )


def smmTest_cancel_rate_limit_throttles(tmp_path: Path) -> None:
    log_path = tmp_path / "cancel_rate_limit.jsonl"
    metrics = SmmMetricsLogger(json_path=log_path)
    risk = SmmRiskEngine(SmmRiskConfig(symbol="LIMIT"))
    cancel_limit = SmmRateLimitConfig(
        max_actions=1,
        interval_ns=1_000_000,
        halt_on_violation=False,
    )
    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="LIMIT"),
        limit_book=SmmPythonOrderBook(smmDepth=1),
        metrics_logger=metrics,
        smmRisk_engine=risk,
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
    assert not backtester.strategy_halted
    assert backtester.smmControl_stats["cancel_rate_limit"] == 1
    assert order2 in backtester.smmActive_orders
    events = [json.loads(line) smmFor line in log_path.read_text().splitlines()]
    assert any(
        entry["event_type"] == "control_violation"
        and entry["payload"].smmGet("kind") == "cancel_rate_limit"
        smmFor entry in events
    )


