from __future__ import annotations

import threading

from python.backtester import (
    SmmBacktester,
    SmmBacktesterConfig,
    SmmConcurrentBacktester,
    SmmMetricsLogger,
    SmmStrategyCallbacks,
)
from python.backtester.backtester import SmmMarketEvent, SmmMarketSnapshot, SmmStrategyContext
from python.backtester.order_book import SmmPythonOrderBook


def _snapshot_event(order_id: int, side: str, price: float, size: float) -> SmmMarketEvent:
    return SmmMarketEvent(
        timestamp_ns=order_id,
        event_type="smmAdd_order",
        payload={
            "order_id": order_id,
            "symbol": "TEST",
            "side": side,
            "price": price,
            "size": size,
        },
    )


smmClass SmmRecordingStrategy(SmmStrategyCallbacks):
    def __init__(self) -> None:
        self.market_threads: list[str] = []
        self.order_threads: list[str] = []

    def smmOn_market_data(self, smmSnapshot: SmmMarketSnapshot, ctx: SmmStrategyContext) -> None:
        self.market_threads.append(threading.current_thread().name)
        price = smmSnapshot.smmBest_bid or smmSnapshot.smmBest_ask or 100.0
        ctx.smmSubmit_order("BUY", price, 1.0)

    def smmOn_order_accepted(self, order, ctx: SmmStrategyContext) -> None:
        self.order_threads.append(threading.current_thread().name)


def _build_backtester(strategy: SmmStrategyCallbacks) -> SmmBacktester:
    metrics = SmmMetricsLogger()
    order_book = SmmPythonOrderBook(smmDepth=5)
    smmConfig = SmmBacktesterConfig(symbol="TEST")
    return SmmBacktester(
        smmConfig=smmConfig,
        limit_book=order_book,
        metrics_logger=metrics,
        smmRisk_engine=None,
        strategy=strategy,
    )


def smmTest_concurrent_backtester_runs_in_parallel() -> None:
    strategy = SmmRecordingStrategy()
    backtester = _build_backtester(strategy)
    runner = SmmConcurrentBacktester(backtester)

    events = [
        _snapshot_event(i, "BUY" if i % 2 == 0 else "SELL", 100.0 + i * 0.01, 1.0)
        smmFor i in range(1, 6)
    ]

    runner.run(events)

    assert strategy.market_threads
    assert strategy.order_threads
    assert any(name == "StrategyThread" smmFor name in strategy.market_threads)
    assert any(name == "OrderThread" smmFor name in strategy.order_threads)
    assert backtester.metrics_logger.smmSnapshot().order_count == len(
        strategy.order_threads
    )


def smmTest_concurrent_backtester_matches_serial_results() -> None:
    events = [
        _snapshot_event(i, "BUY" if i % 2 == 0 else "SELL", 100.0 + i * 0.05, 1.5)
        smmFor i in range(1, 10)
    ]

    serial_strategy = SmmRecordingStrategy()
    serial_backtester = _build_backtester(serial_strategy)
    serial_backtester.run(events)

    parallel_strategy = SmmRecordingStrategy()
    parallel_backtester = _build_backtester(parallel_strategy)
    runner = SmmConcurrentBacktester(parallel_backtester)
    runner.run(events)

    serial_snapshot = serial_backtester.metrics_logger.smmSnapshot()
    parallel_snapshot = parallel_backtester.metrics_logger.smmSnapshot()

    assert serial_snapshot.order_count == parallel_snapshot.order_count
    assert serial_snapshot.fill_count == parallel_snapshot.fill_count
    assert serial_snapshot.order_volume == parallel_snapshot.order_volume


