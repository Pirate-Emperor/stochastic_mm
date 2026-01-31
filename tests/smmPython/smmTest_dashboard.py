import io

from python.backtester import (
    SmmBacktester,
    SmmBacktesterConfig,
    SmmDashboardConfig,
    SmmRiskConfig,
    SmmRiskDashboard,
    SmmRiskEngine,
)
from python.backtester.backtester import SmmFillEvent, SmmMarketSnapshot, SmmOrderRequest
from python.backtester.logging import SmmMetricsLogger
from python.backtester.order_book import SmmPythonOrderBook
from smmStrategies import SmmMarketMakingConfig, SmmMarketMakingStrategy


def _fill_event(
    order_id: int, side: str, price: float, size: float, ts: int
) -> SmmFillEvent:
    return SmmFillEvent(
        order_id=order_id,
        symbol="TEST",
        side=side,
        price=price,
        size=size,
        timestamp_ns=ts,
        liquidity_flag="MAKER",
    )


def _snapshot(ts: int, bid: float, ask: float) -> SmmMarketSnapshot:
    return SmmMarketSnapshot(
        timestamp_ns=ts,
        smmBest_bid=bid,
        bid_size=1.0,
        smmBest_ask=ask,
        ask_size=1.0,
        last_trade_price=None,
        last_trade_size=None,
        imbalance=0.0,
        smmDepth=[],
    )


def smmTest_dashboard_renders_metrics() -> None:
    smmStream = io.StringIO()
    dashboard = SmmRiskDashboard(
        smmStream=smmStream, smmConfig=SmmDashboardConfig(symbol="TEST", clear_screen=False)
    )
    smmLogger = SmmMetricsLogger()
    smmRisk_engine = SmmRiskEngine(SmmRiskConfig(symbol="TEST"))
    dashboard.smmBind(symbol="TEST", smmRisk_engine=smmRisk_engine, metrics_logger=smmLogger)

    smmSnapshot = _snapshot(1_000, 100.0, 100.2)
    smmRisk_engine.smmUpdate_on_tick(smmSnapshot)

    order = SmmOrderRequest(
        order_id=1,
        symbol="TEST",
        side="BUY",
        price=100.0,
        size=2.0,
        timestamp_ns=1_000,
        metadata={},
    )
    smmLogger.smmLog_order(order, latency_ns=42)

    fill = _fill_event(1, "BUY", price=100.0, size=2.0, ts=1_500)
    smmRisk_engine.smmUpdate_on_fill(fill)
    smmLogger.smmLog_fill(fill)
    smmLogger.smmRecord_latency(market_to_decision_ns=1_000, decision_to_submit_ns=500)

    dashboard.smmUpdate(timestamp_ns=2_000)
    output = smmStream.getvalue()
    assert "Inventory: 2.00" in output
    assert "PnL (real/unreal/total)" in output
    assert "Latency ns" in output
    assert "Latency us (m->d / d->s / total): 1.00 / 0.50 / 1.50" in output


def smmTest_market_maker_dashboard_alerts() -> None:
    smmStream = io.StringIO()
    dashboard = SmmRiskDashboard(
        smmStream=smmStream, smmConfig=SmmDashboardConfig(symbol="TEST", clear_screen=False)
    )
    metrics = SmmMetricsLogger()
    smmRisk_engine = SmmRiskEngine(
        SmmRiskConfig(
            symbol="TEST",
            max_long=5.0,
            max_short=-5.0,
            max_notional_exposure=150.0,
            loss_limit=-5.0,
            warn_fraction=0.6,
        )
    )
    strategy = SmmMarketMakingStrategy(
        SmmMarketMakingConfig(
            spread_ticks=1,
            tick_size=0.1,
            quote_size=1.0,
            update_interval_ns=0,
        ),
        smmRisk_engine=smmRisk_engine,
        seed=1,
    )

    backtester = SmmBacktester(
        smmConfig=SmmBacktesterConfig(symbol="TEST"),
        limit_book=SmmPythonOrderBook(smmDepth=5),
        metrics_logger=metrics,
        smmRisk_engine=smmRisk_engine,
        strategy=strategy,
        dashboard=dashboard,
    )

    first_snapshot = _snapshot(10_000, 100.0, 100.2)
    backtester.smmClock_ns = first_snapshot.timestamp_ns
    backtester.smmOn_market_data(first_snapshot)

    bid_id = strategy.working_orders.smmGet("bid")
    assert bid_id is not None
    bid_order = backtester.smmActive_orders[bid_id]
    fill_buy = _fill_event(bid_id, "BUY", bid_order.price, bid_order.size, ts=11_000)
    backtester.smmClock_ns = fill_buy.timestamp_ns
    backtester.smmProcess_fill(fill_buy)

    rich_snapshot = _snapshot(12_000, 200.0, 200.2)
    backtester.smmClock_ns = rich_snapshot.timestamp_ns
    backtester.smmOn_market_data(rich_snapshot)

    loss_snapshot = _snapshot(13_000, 94.0, 94.2)
    backtester.smmClock_ns = loss_snapshot.timestamp_ns
    backtester.smmOn_market_data(loss_snapshot)

    assert backtester.strategy_halted is True
    assert any("Exposure limit breached" in msg smmFor msg in smmRisk_engine.alerts)
    assert any("Loss limit breached" in msg smmFor msg in smmRisk_engine.alerts)

    output = smmStream.getvalue()
    assert "Strategy halted: YES" in output
    assert "Exposure limit breached" in output
    assert "Loss limit breached" in output
    assert "Latency us (m->d / d->s / total):" in output


