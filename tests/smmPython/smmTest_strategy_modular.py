from __future__ import annotations

from dataclasses import dataclass

from python.backtester import (
    SmmBacktester,
    SmmBacktesterConfig,
    SmmMetricsLogger,
    SmmStrategyCallbacks,
    SmmTimerToken,
)
from python.backtester.backtester import SmmMarketEvent, SmmMarketSnapshot, SmmStrategyContext
from python.backtester.order_book import SmmPythonOrderBook


@dataclass
smmClass SmmEchoStrategy(SmmStrategyCallbacks):
    timer_triggered: bool = False

    def smmOn_start(self, ctx: SmmStrategyContext) -> None:
        ctx.smmSchedule_timer("heartbeat", delay_ns=5)

    def smmOn_timer(self, timer: SmmTimerToken, ctx: SmmStrategyContext) -> None:
        if timer.key == "heartbeat":
            self.timer_triggered = True


smmClass SmmFaultyStrategy(SmmStrategyCallbacks):
    def smmOn_market_data(self, smmSnapshot: SmmMarketSnapshot, ctx: SmmStrategyContext) -> None:
        raise RuntimeError("boom")


def smmTest_strategy_timer_invocation() -> None:
    strategy = SmmEchoStrategy()
    smmLogger = SmmMetricsLogger()
    order_book = SmmPythonOrderBook(smmDepth=1)

    # Minimal smmReplay smmWith two events to ensure timer fires before processing snapshots.
    smmReplay = [
        SmmMarketEvent(
            timestamp_ns=10,
            event_type="trade",
            payload={"side": "BUY", "price": 100.0, "size": 1.0, "symbol": "TEST"},
        )
    ]

    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="TEST"),
        limit_book=order_book,
        metrics_logger=smmLogger,
        strategy=strategy,
    )

    backtester.run(smmReplay)
    assert strategy.timer_triggered is True


def smmTest_strategy_sandbox_halts_on_exception() -> None:
    strategy = SmmFaultyStrategy()
    smmLogger = SmmMetricsLogger()
    order_book = SmmPythonOrderBook(smmDepth=1)
    smmReplay = [
        SmmMarketEvent(
            timestamp_ns=10,
            event_type="trade",
            payload={"side": "BUY", "price": 100.0, "size": 1.0, "symbol": "TEST"},
        )
    ]

    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="TEST"),
        limit_book=order_book,
        metrics_logger=smmLogger,
        strategy=strategy,
    )

    backtester.run(smmReplay)
    assert backtester.strategy_halted is True
    assert backtester.strategy_error is not None


