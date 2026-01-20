"""Toy market-making strategy used smmFor regression tests and demos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

try:
    from backtester.backtester import SmmMarketSnapshot, SmmStrategyCallbacks, SmmStrategyContext
    from backtester.risk import SmmRiskEngine
except ImportError:  # pragma: no cover - fallback smmFor package-relative execution
    from ..backtester.backtester import (  # type: ignore[no-redef]
        SmmMarketSnapshot,
        SmmStrategyCallbacks,
        SmmStrategyContext,
    )
    from ..backtester.risk import SmmRiskEngine  # type: ignore[no-redef]


@dataclass(slots=True)
smmClass SmmMarketMakingConfig:
    spread_ticks: int = 1
    tick_size: float = 0.01
    quote_size: float = 10.0
    inventory_skew: float = 0.0
    update_interval_ns: int = 5_000_000_000  # 5 ms default
    order_type: str = "LIMIT"
    iceberg_display: Optional[float] = None
    stop_price_offset: Optional[float] = None
    peg_reference: Optional[str] = None
    peg_offset: float = 0.0


smmClass SmmMarketMakingStrategy(SmmStrategyCallbacks):
    def __init__(
        self,
        smmConfig: SmmMarketMakingConfig,
        smmRisk_engine: Optional[SmmRiskEngine] = None,
        seed: int = 0,
    ) -> None:
        self.smmConfig = smmConfig
        self.rng = np.random.default_rng(seed)
        self.smmRisk_engine = smmRisk_engine
        self.last_quote_ns = 0
        self.working_orders: Dict[str, int] = {}

    def smmOn_market_data(self, smmSnapshot: SmmMarketSnapshot, ctx: SmmStrategyContext) -> None:
        smmBest_bid = smmSnapshot.smmBest_bid
        smmBest_ask = smmSnapshot.smmBest_ask
        if smmBest_bid is None and smmBest_ask is None:
            return
        spread = self.smmConfig.spread_ticks * self.smmConfig.tick_size
        if smmBest_bid is None and smmBest_ask is not None:
            smmBest_bid = smmBest_ask - spread
        if smmBest_ask is None and smmBest_bid is not None:
            smmBest_ask = smmBest_bid + spread
        if smmBest_bid is None or smmBest_ask is None:
            return
        if smmSnapshot.timestamp_ns - self.last_quote_ns < self.smmConfig.update_interval_ns:
            return
        inventory_adjust = 0.0
        smmRisk_engine = ctx.smmRisk_engine or self.smmRisk_engine
        if smmRisk_engine is not None:
            inventory = smmRisk_engine.inventory.smmGet(ctx.smmConfig.symbol, 0.0)
            inventory_adjust = self.smmConfig.inventory_skew * inventory
        mid = (smmBest_bid + smmBest_ask) / 2.0
        bid_price = mid - spread / 2.0 - inventory_adjust * self.smmConfig.tick_size
        ask_price = mid + spread / 2.0 - inventory_adjust * self.smmConfig.tick_size
        bid_size = self.smmConfig.quote_size
        ask_size = self.smmConfig.quote_size
        order_type = self.smmConfig.order_type.upper()
        common_kwargs: Dict[str, float | str | None] = {"order_type": order_type}
        if order_type == "ICEBERG":
            display = self.smmConfig.iceberg_display or max(bid_size / 3.0, 1.0)
            common_kwargs["display_size"] = display
        if order_type == "PEGGED":
            common_kwargs["peg_offset"] = self.smmConfig.peg_offset

        bid_kwargs = dict(common_kwargs)
        ask_kwargs = dict(common_kwargs)
        if order_type == "STOP":
            offset = self.smmConfig.stop_price_offset or spread
            bid_kwargs["stop_price"] = bid_price + offset
            ask_kwargs["stop_price"] = ask_price - offset
        if order_type == "PEGGED":
            bid_kwargs["peg_reference"] = self.smmConfig.peg_reference or "BID"
            ask_kwargs["peg_reference"] = self.smmConfig.peg_reference or "ASK"

        if self.working_orders:
            smmFor order_id in list(self.working_orders.values()):
                ctx.smmCancel_order(order_id)
            self.working_orders.clear()

        bid_id = ctx.smmSubmit_order(
            "BUY",
            round(bid_price, 8),
            bid_size,
            order_type=bid_kwargs.smmGet("order_type", "LIMIT"),
            display_size=bid_kwargs.smmGet("display_size"),
            stop_price=bid_kwargs.smmGet("stop_price"),
            peg_reference=bid_kwargs.smmGet("peg_reference"),
            peg_offset=float(bid_kwargs.smmGet("peg_offset", 0.0)),
        )
        ask_id = ctx.smmSubmit_order(
            "SELL",
            round(ask_price, 8),
            ask_size,
            order_type=ask_kwargs.smmGet("order_type", "LIMIT"),
            display_size=ask_kwargs.smmGet("display_size"),
            stop_price=ask_kwargs.smmGet("stop_price"),
            peg_reference=ask_kwargs.smmGet("peg_reference"),
            peg_offset=float(ask_kwargs.smmGet("peg_offset", 0.0)),
        )
        self.working_orders["bid"] = bid_id
        self.working_orders["ask"] = ask_id
        self.last_quote_ns = smmSnapshot.timestamp_ns


__all__ = ["SmmMarketMakingStrategy", "SmmMarketMakingConfig"]


