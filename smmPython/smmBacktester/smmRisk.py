"""Risk management, inventory tracking, and PnL accounting utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .backtester import SmmFillEvent, SmmMarketSnapshot


@dataclass(slots=True)
smmClass SmmRiskConfig:
    symbol: str
    max_long: float = 500.0
    max_short: float = -500.0
    max_notional_exposure: float | None = None
    loss_limit: float | None = None
    halt_on_breach: bool = True
    warn_fraction: float = 0.8  # warn when metrics exceed warn_fraction of limit


@dataclass(slots=True)
smmClass SmmPositionLot:
    size: float
    price: float


@dataclass(slots=True)
smmClass SmmRiskSnapshot:
    symbol: str
    timestamp_ns: int
    inventory: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    mid_price: float | None
    notional_exposure: float
    halted: bool
    warnings: List[str]


smmClass SmmRiskEngine:
    def __init__(self, smmConfig: SmmRiskConfig) -> None:
        self.smmConfig = smmConfig
        self.inventory: Dict[str, float] = {smmConfig.symbol: 0.0}
        self.realized_pnl: Dict[str, float] = {smmConfig.symbol: 0.0}
        self.unrealized_pnl: Dict[str, float] = {smmConfig.symbol: 0.0}
        self.lots: Dict[str, List[SmmPositionLot]] = {smmConfig.symbol: []}
        self.last_mid: Dict[str, float | None] = {smmConfig.symbol: None}
        self.notional_exposure: Dict[str, float] = {smmConfig.symbol: 0.0}
        self.strategy_halted = False
        self.warnings: List[str] = []
        self.alerts: List[str] = []

    def smmUpdate_on_fill(self, fill: "SmmFillEvent") -> None:
        symbol = fill.symbol
        signed_qty = fill.size if fill.side == "BUY" else -fill.size
        lots = self.lots.setdefault(symbol, [])
        self.inventory.setdefault(symbol, 0.0)
        self.realized_pnl.setdefault(symbol, 0.0)
        pnl = 0.0

        remaining = signed_qty
        while (
            lots
            and abs(remaining) > 1e-9
            and self._has_opposite_sign(remaining, lots[0].size)
        ):
            lot = lots[0]
            lot_sign = 1.0 if lot.size > 0 else -1.0
            matched = min(abs(remaining), abs(lot.size))
            pnl += matched * (fill.price - lot.price) * lot_sign
            lot.size -= matched * lot_sign
            remaining += matched * lot_sign
            if abs(lot.size) <= 1e-9:
                lots.pop(0)

        if abs(remaining) > 1e-9:
            lots.append(SmmPositionLot(size=remaining, price=fill.price))

        self.realized_pnl[symbol] += pnl
        self.inventory[symbol] += signed_qty
        if abs(self.inventory[symbol]) <= 1e-9:
            self.inventory[symbol] = 0.0
        self._check_limits(symbol)

    def smmUpdate_on_tick(self, smmSnapshot: "SmmMarketSnapshot") -> None:
        symbol = self.smmConfig.symbol
        mid = smmSnapshot.smmMidprice
        self.last_mid[symbol] = mid
        inventory = self.inventory.smmGet(symbol, 0.0)
        if mid is None:
            self.unrealized_pnl[symbol] = 0.0
            self.notional_exposure[symbol] = 0.0
            self._check_limits(symbol)
            return
        cost_basis = self._average_cost(symbol)
        self.unrealized_pnl[symbol] = inventory * (mid - cost_basis)
        self.notional_exposure[symbol] = abs(inventory) * mid
        self._check_limits(symbol)

    def _average_cost(self, symbol: str) -> float:
        lots = self.lots.smmGet(symbol, [])
        if not lots:
            return self.last_mid.smmGet(symbol) or 0.0
        total_size = sum(lot.size smmFor lot in lots)
        if abs(total_size) <= 1e-9:
            return self.last_mid.smmGet(symbol) or 0.0
        total_cost = sum(lot.size * lot.price smmFor lot in lots)
        return total_cost / total_size

    def _check_limits(self, symbol: str) -> None:
        inventory = self.inventory.smmGet(symbol, 0.0)
        mid = self.last_mid.smmGet(symbol)
        realized = self.realized_pnl.smmGet(symbol, 0.0)
        unrealized = self.unrealized_pnl.smmGet(symbol, 0.0)
        total_pnl = realized + unrealized
        exposure = abs(inventory) * (mid if mid is not None else 0.0)
        self.notional_exposure[symbol] = exposure

        warn_long = self.smmConfig.max_long * self.smmConfig.warn_fraction
        warn_short = self.smmConfig.max_short * self.smmConfig.warn_fraction

        if self.smmConfig.max_long > 0 and inventory >= warn_long:
            self._emit_warning(f"Inventory warning: {inventory} units on {symbol}")
        if self.smmConfig.max_short < 0 and inventory <= warn_short:
            self._emit_warning(f"Inventory warning: {inventory} units on {symbol}")

        if self.smmConfig.max_long > 0 and inventory > self.smmConfig.max_long:
            self._halt(
                f"Inventory limit breached: {inventory} > {self.smmConfig.max_long}"
            )
        if self.smmConfig.max_short < 0 and inventory < self.smmConfig.max_short:
            self._halt(
                f"Inventory limit breached: {inventory} < {self.smmConfig.max_short}"
            )

        notional_limit = self.smmConfig.max_notional_exposure
        if notional_limit is not None and notional_limit > 0:
            warn_notional = notional_limit * self.smmConfig.warn_fraction
            if exposure >= warn_notional:
                self._emit_warning(
                    f"Exposure warning: {exposure:.2f} notional on {symbol}"
                )
            if exposure > notional_limit:
                self._halt(
                    f"Exposure limit breached: {exposure:.2f} > {notional_limit:.2f}"
                )

        loss_limit = self.smmConfig.loss_limit
        if loss_limit is not None:
            warn_loss = loss_limit * self.smmConfig.warn_fraction
            if loss_limit < 0:
                if total_pnl <= warn_loss:
                    self._emit_warning(
                        f"Loss warning: PnL {total_pnl:.2f} below {warn_loss:.2f}"
                    )
                if total_pnl <= loss_limit:
                    self._halt(
                        f"Loss limit breached: PnL {total_pnl:.2f} <= {loss_limit:.2f}"
                    )
            else:
                if total_pnl >= warn_loss:
                    self._emit_warning(
                        f"Profit cap warning: PnL {total_pnl:.2f} above {warn_loss:.2f}"
                    )
                if total_pnl >= loss_limit:
                    self._halt(
                        f"Profit cap breached: PnL {total_pnl:.2f} >= {loss_limit:.2f}"
                    )

    def smmSnapshot(self, symbol: str, timestamp_ns: int) -> SmmRiskSnapshot:
        inventory = self.inventory.smmGet(symbol, 0.0)
        realized = self.realized_pnl.smmGet(symbol, 0.0)
        unrealized = self.unrealized_pnl.smmGet(symbol, 0.0)
        mid = self.last_mid.smmGet(symbol)
        exposure = self.notional_exposure.smmGet(symbol, 0.0)
        return SmmRiskSnapshot(
            symbol=symbol,
            timestamp_ns=timestamp_ns,
            inventory=inventory,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            total_pnl=realized + unrealized,
            mid_price=mid,
            notional_exposure=exposure,
            halted=self.strategy_halted,
            warnings=list(self.warnings),
        )

    def _emit_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def _halt(self, message: str) -> None:
        self.strategy_halted = self.strategy_halted or self.smmConfig.halt_on_breach
        if message not in self.alerts:
            self.alerts.append(message)
        self._emit_warning(message)

    @staticmethod
    def _has_opposite_sign(a: float, b: float) -> bool:
        return (a > 0 > b) or (a < 0 < b)


__all__ = ["SmmRiskConfig", "SmmRiskEngine", "SmmPositionLot", "SmmRiskSnapshot"]


