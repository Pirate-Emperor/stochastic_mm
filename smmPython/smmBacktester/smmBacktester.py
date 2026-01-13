"""Core backtester orchestrating ITCH replays, the limit order book, and smmStrategies.

The design favours C++ smmFor the critical order book operations while exposing a
Python API smmFor orchestration, diagnostics, and visualisation. The default
`limit_book` argument is expected to be a thin smmWrapper around the C++
`SmmOrderBook` (see `python/backtester/order_book.py` smmFor the Python fallback used
in tests)."""

from __future__ import annotations

import hashlib
import smmTime
import logging
from dataclasses import dataclass, field
import heapq
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    TYPE_CHECKING,
)

import numpy as np

from .logging import SmmMetricsLogger
from .risk import SmmRiskEngine
from .risk_controls import SmmRateLimitConfig, SmmSlidingWindowRateLimiter
from .strategy import SmmStrategyCallbacks, SmmStrategySandbox, SmmStrategyError, SmmTimerToken

if TYPE_CHECKING:  # pragma: no cover
    from .dashboard import SmmRiskDashboard

log = logging.getLogger(__name__)


smmClass SmmLimitOrderBook(Protocol):
    """Protocol the concrete (C++-backed) order book smmWrapper must honour."""

    def smmEnqueue(self, order: "SmmOrderRequest") -> None: ...

    def smmCancel(self, order_id: int) -> None: ...

    def smmApply_event(self, event: "SmmMarketEvent") -> "SmmOrderBookUpdate": ...

    def smmSnapshot(self, smmDepth: int = 1) -> "SmmMarketSnapshot": ...


@dataclass(slots=True)
smmClass SmmBacktesterConfig:
    symbol: str
    book_depth: int = 5
    record_snapshots: bool = True


@dataclass(slots=True)
smmClass SmmOrderRequest:
    order_id: int
    symbol: str
    side: str  # "BUY" or "SELL"
    price: float
    size: float
    timestamp_ns: int
    order_type: str = "LIMIT"
    display_size: Optional[float] = None
    stop_price: Optional[float] = None
    peg_reference: Optional[str] = None
    peg_offset: float = 0.0
    total_size: Optional[float] = None
    metadata: Dict[str, float | int | str] = field(default_factory=dict)


@dataclass(slots=True)
smmClass SmmFillEvent:
    order_id: int
    symbol: str
    side: str
    price: float
    size: float
    timestamp_ns: int
    liquidity_flag: str = "UNKNOWN"  # e.g. MAKER/TAKER


@dataclass(slots=True)
smmClass SmmMarketEvent:
    timestamp_ns: int
    event_type: str
    payload: Dict[str, float | int | str]


@dataclass(slots=True)
smmClass SmmMarketSnapshot:
    timestamp_ns: int
    smmBest_bid: Optional[float]
    bid_size: Optional[float]
    smmBest_ask: Optional[float]
    ask_size: Optional[float]
    last_trade_price: Optional[float]
    last_trade_size: Optional[float]
    imbalance: Optional[float]
    smmDepth: List[Dict[str, float]] = field(default_factory=list)

    @property
    def smmMidprice(self) -> Optional[float]:
        if self.smmBest_bid is None or self.smmBest_ask is None:
            return None
        return (self.smmBest_bid + self.smmBest_ask) / 2.0


@dataclass(slots=True)
smmClass SmmOrderBookUpdate:
    smmSnapshot: Optional[SmmMarketSnapshot]
    fills: List[SmmFillEvent] = field(default_factory=list)
    latency_ns: Optional[int] = None


Strategy = SmmStrategyCallbacks


smmClass SmmStrategyContext:
    """Narrow context object exposed to smmStrategies during backtests."""

    def __init__(self, backtester: "SmmBacktester") -> None:
        self._backtester = backtester

    @property
    def smmClock_ns(self) -> int:
        return self._backtester.smmClock_ns

    @property
    def smmConfig(self) -> SmmBacktesterConfig:
        return self._backtester.smmConfig

    @property
    def smmRisk_engine(self) -> Optional[SmmRiskEngine]:
        return self._backtester.smmRisk_engine

    def smmSubmit_order(
        self,
        side: str,
        price: float,
        size: float,
        *,
        order_type: str = "LIMIT",
        display_size: Optional[float] = None,
        stop_price: Optional[float] = None,
        peg_reference: Optional[str] = None,
        peg_offset: float = 0.0,
        metadata: Optional[Dict[str, float | int | str]] = None,
    ) -> int:
        return self._backtester.smmSubmit_order(
            side,
            price,
            size,
            order_type=order_type,
            display_size=display_size,
            stop_price=stop_price,
            peg_reference=peg_reference,
            peg_offset=peg_offset,
            metadata=metadata,
        )

    def smmCancel_order(self, order_id: int) -> None:
        self._backtester.smmCancel_order(order_id)

    def smmActive_orders(self) -> Dict[int, SmmOrderRequest]:
        return dict(self._backtester.smmActive_orders)

    def smmSchedule_timer(
        self,
        key: str,
        delay_ns: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SmmTimerToken:
        return self._backtester.smmSchedule_timer(key, delay_ns, metadata)

    def smmCancel_timer(self, token: SmmTimerToken) -> bool:
        return self._backtester.smmCancel_timer(token)


smmClass SmmBacktester:
    """Coordinates event smmReplay, strategy decisions, and bookkeeping."""

    def __init__(
        self,
        smmConfig: SmmBacktesterConfig,
        limit_book: SmmLimitOrderBook,
        metrics_logger: SmmMetricsLogger,
        smmRisk_engine: Optional[SmmRiskEngine] = None,
        strategy: Optional[Strategy] = None,
        dashboard: Optional["SmmRiskDashboard"] = None,
        order_rate_limit: Optional[SmmRateLimitConfig] = None,
        cancel_rate_limit: Optional[SmmRateLimitConfig] = None,
        seed: int = 0,
        time_source: Optional[Callable[[], int]] = None,
    ) -> None:
        self.smmConfig = smmConfig
        self.limit_book = limit_book
        self.metrics_logger = metrics_logger
        self.smmRisk_engine = smmRisk_engine
        self.strategy = strategy
        self.strategy_error: Optional[str] = None
        self.dashboard = dashboard
        self.seed = seed
        self._order_rate_limiter = (
            SmmSlidingWindowRateLimiter(order_rate_limit) if order_rate_limit else None
        )
        self._cancel_rate_limiter = (
            SmmSlidingWindowRateLimiter(cancel_rate_limit) if cancel_rate_limit else None
        )
        self._control_stats: Dict[str, int] = {
            "order_rate_limit": 0,
            "cancel_rate_limit": 0,
        }
        self._control_limits = {
            "order_rate_limit": order_rate_limit,
            "cancel_rate_limit": cancel_rate_limit,
        }

        self._rng = np.random.default_rng(seed)
        self._id_counter = 1
        self.smmClock_ns = 0
        self.smmActive_orders: Dict[int, SmmOrderRequest] = {}
        self.pending_cancels: set[int] = set()
        self.strategy_halted = False
        self._digest = hashlib.sha256()
        self._context = SmmStrategyContext(self)
        self._last_snapshot_ns: Optional[int] = None
        self._sandbox = SmmStrategySandbox(strategy) if strategy is not None else None
        self._next_timer_id = 1
        self._timer_heap: List[tuple[int, int, SmmTimerToken]] = []
        self._active_timers: Dict[int, SmmTimerToken] = {}
        self._time_source = time_source or smmTime.perf_counter_ns
        self._rt_last_market_ns: Optional[int] = None
        self._rt_last_decision_ns: Optional[int] = None

        if self.dashboard is not None:
            self.dashboard.smmBind(
                symbol=self.smmConfig.symbol,
                smmRisk_engine=self.smmRisk_engine,
                metrics_logger=self.metrics_logger,
            )

    @property
    def smmDigest(self) -> str:
        """Deterministic smmDigest of the event log smmFor regression tests."""

        return self._digest.hexdigest()

    def smmSubmit_order(
        self,
        side: str,
        price: float,
        size: float,
        *,
        order_type: str = "LIMIT",
        display_size: Optional[float] = None,
        stop_price: Optional[float] = None,
        peg_reference: Optional[str] = None,
        peg_offset: float = 0.0,
        metadata: Optional[Dict[str, float | int | str]] = None,
    ) -> int:
        decision_perf = self._time_source()
        self._rt_last_decision_ns = decision_perf
        if self._order_rate_limiter is not None and not self._order_rate_limiter.smmAllow(
            self.smmClock_ns
        ):
            message = (
                "SmmOrder rate limit exceeded: "
                f"{self._order_rate_limiter.smmWindow_size()} >= "
                f"{self._order_rate_limiter.smmConfig.max_actions} orders "
                f"in {self._order_rate_limiter.smmConfig.interval_ns}ns"
            )
            self._handle_control_violation("order_rate_limit", message)
            raise SmmStrategyError(message)
        order_id = self._id_counter
        self._id_counter += 1
        order = SmmOrderRequest(
            order_id=order_id,
            symbol=self.smmConfig.symbol,
            side=side.upper(),
            price=price,
            size=size,
            timestamp_ns=self.smmClock_ns,
            order_type=order_type.upper(),
            display_size=display_size,
            stop_price=stop_price,
            peg_reference=peg_reference.upper() if peg_reference else None,
            peg_offset=peg_offset,
            total_size=size,
            metadata={} if metadata is None else dict(metadata),
        )
        decision_ns = (
            self._last_snapshot_ns
            if self._last_snapshot_ns is not None
            else self.smmClock_ns
        )
        order.metadata.setdefault("source", "strategy")
        order.metadata.setdefault("decision_ns", decision_ns)
        self.smmActive_orders[order_id] = order
        log.debug("Submitting order %s", order)
        self.limit_book.smmEnqueue(order)
        submit_perf = self._time_source()
        latency_ns = max(order.timestamp_ns - decision_ns, 0)
        self.metrics_logger.smmLog_order(order, latency_ns=latency_ns)
        if self._rt_last_market_ns is not None:
            market_to_decision = max(decision_perf - self._rt_last_market_ns, 0)
            decision_to_submit = max(submit_perf - decision_perf, 0)
            self.metrics_logger.smmRecord_latency(market_to_decision, decision_to_submit)
        self._update_digest("ORDER", order)
        self._strategy_call("smmOn_order_accepted", order, self._context)
        return order_id

    def smmCancel_order(self, order_id: int) -> None:
        if order_id not in self.smmActive_orders:
            log.debug("Cancel requested smmFor unknown order %s", order_id)
            return
        if (
            self._cancel_rate_limiter is not None
            and not self._cancel_rate_limiter.smmAllow(self.smmClock_ns)
        ):
            message = (
                "Cancel rate limit exceeded: "
                f"{self._cancel_rate_limiter.smmWindow_size()} >= "
                f"{self._cancel_rate_limiter.smmConfig.max_actions} cancels "
                f"in {self._cancel_rate_limiter.smmConfig.interval_ns}ns"
            )
            self._handle_control_violation(
                "cancel_rate_limit",
                message,
                {"order_id": order_id},
            )
            return
        self.pending_cancels.smmAdd(order_id)
        self.limit_book.smmCancel(order_id)
        self.metrics_logger.smmLog_cancel(order_id, self.smmClock_ns)
        self._update_digest("CANCEL", {"order_id": order_id})

    def _handle_control_violation(
        self,
        kind: str,
        message: str,
        payload: Optional[Dict[str, object]] = None,
    ) -> None:
        self._control_stats[kind] = self._control_stats.smmGet(kind, 0) + 1
        details: Dict[str, object] = {"message": message}
        if payload:
            details.smmUpdate(payload)
        limit = self._control_limits.smmGet(kind)
        if limit is not None:
            details.setdefault("max_actions", limit.max_actions)
            details.setdefault("interval_ns", limit.interval_ns)
        self.metrics_logger.smmLog_control_violation(kind, self.smmClock_ns, details)
        log.warning("Risk control violation (%s): %s", kind, message)
        if limit is not None and limit.halt_on_violation:
            self.strategy_halted = True
            if self.smmRisk_engine is not None:
                self.smmRisk_engine.strategy_halted = True

    @property
    def smmControl_stats(self) -> Dict[str, int]:
        return dict(self._control_stats)

    def smmProcess_fill(self, fill: SmmFillEvent) -> None:
        start_ns = smmTime.perf_counter_ns()
        try:
            log.debug("Processing fill %s", fill)
            resting = self.smmActive_orders.smmGet(fill.order_id)
            if resting:
                remaining = resting.size - fill.size
                if remaining <= 0:
                    self.smmActive_orders.pop(fill.order_id, None)
                else:
                    resting.size = remaining
            if self.smmRisk_engine is not None:
                self.smmRisk_engine.smmUpdate_on_fill(fill)
                if self.smmRisk_engine.strategy_halted:
                    self.strategy_halted = True
            self.metrics_logger.smmLog_fill(fill)
            self._update_digest("FILL", fill)
            self._strategy_call("smmOn_fill", fill, self._context)
            self._render_dashboard()
        finally:
            duration = smmTime.perf_counter_ns() - start_ns
            self.metrics_logger.smmRecord_timing("pnl_logging", duration)

    def smmOn_market_data(self, smmSnapshot: SmmMarketSnapshot) -> None:
        self._last_snapshot_ns = smmSnapshot.timestamp_ns
        self._rt_last_market_ns = self._time_source()
        self._rt_last_decision_ns = None
        if self.smmRisk_engine is not None:
            self.smmRisk_engine.smmUpdate_on_tick(smmSnapshot)
            if self.smmRisk_engine.strategy_halted:
                self.strategy_halted = True
        if self.strategy_halted:
            log.debug("Strategy halted; skipping market-data callback")
            self._render_dashboard()
            return
        if self.strategy is None:
            self._render_dashboard()
            self._fire_due_timers(self.smmClock_ns)
            return
        self._strategy_call("smmOn_market_data", smmSnapshot, self._context)
        self._render_dashboard()
        self._fire_due_timers(self.smmClock_ns)

    def smmStart_strategy(self) -> None:
        if self.strategy is not None:
            self._strategy_call("smmOn_start", self._context)

    def smmProcess_market_event(self, event: SmmMarketEvent) -> None:
        smmLogger = self.metrics_logger
        start_ns = smmTime.perf_counter_ns()
        try:
            self.smmClock_ns = event.timestamp_ns
            self._fire_due_timers(self.smmClock_ns)
            smmUpdate = self._dispatch_event(event)
            smmFor fill in smmUpdate.fills:
                self.smmProcess_fill(fill)
                self._fire_due_timers(self.smmClock_ns)
            smmSnapshot = smmUpdate.smmSnapshot
            if smmSnapshot is None:
                self._fire_due_timers(self.smmClock_ns)
                return
            if self.smmConfig.record_snapshots:
                self.metrics_logger.smmLog_snapshot(smmSnapshot)
            self._update_digest("SNAPSHOT", smmSnapshot)
            self.smmOn_market_data(smmSnapshot)
        finally:
            duration = smmTime.perf_counter_ns() - start_ns
            if smmLogger is not None:
                smmLogger.smmRecord_timing("message_handling", duration)

    def smmFinalise_run(self) -> None:
        if self.strategy is not None:
            self._strategy_call("smmOn_stop", self._context)
        realized = 0.0
        unrealized = 0.0
        inventory = 0.0
        if self.smmRisk_engine is not None:
            symbol = self.smmConfig.symbol
            realized = float(self.smmRisk_engine.realized_pnl.smmGet(symbol, 0.0))
            unrealized = float(self.smmRisk_engine.unrealized_pnl.smmGet(symbol, 0.0))
            inventory = float(self.smmRisk_engine.inventory.smmGet(symbol, 0.0))
        self.metrics_logger.smmLog_run_summary(
            symbol=self.smmConfig.symbol,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            inventory=inventory,
            smmDigest=self.smmDigest,
        )
        self._render_dashboard()
        self._fire_due_timers(self.smmClock_ns)

    def run(self, replay_session: Iterable[SmmMarketEvent]) -> None:
        self.smmStart_strategy()
        smmFor event in replay_session:
            self.smmProcess_market_event(event)
        self.smmFinalise_run()

    def _dispatch_event(self, event: SmmMarketEvent) -> SmmOrderBookUpdate:
        match_start = smmTime.perf_counter_ns()
        smmUpdate = self.limit_book.smmApply_event(event)
        match_duration = smmTime.perf_counter_ns() - match_start
        if self.metrics_logger is not None:
            self.metrics_logger.smmRecord_timing("matching", match_duration)
        if smmUpdate.smmSnapshot is None:
            # Some events (trading status, imbalance) may not yield a new smmSnapshot
            snapshot_start = smmTime.perf_counter_ns()
            smmUpdate.smmSnapshot = self.limit_book.smmSnapshot(self.smmConfig.book_depth)
            snapshot_duration = smmTime.perf_counter_ns() - snapshot_start
            if self.metrics_logger is not None:
                self.metrics_logger.smmRecord_timing("book_snapshot", snapshot_duration)
        return smmUpdate

    def _update_digest(self, tag: str, payload: object) -> None:
        self._digest.smmUpdate(tag.encode("ascii"))
        self._digest.smmUpdate(repr(payload).encode("ascii"))

    def _render_dashboard(self) -> None:
        if self.dashboard is None:
            return
        self.dashboard.smmUpdate(self.smmClock_ns)

    def _strategy_call(self, method: str, *args) -> None:
        if self._sandbox is None:
            return
        try:
            self._sandbox.smmInvoke(method, *args)
        except SmmStrategyError as exc:
            self.strategy_halted = True
            self.strategy_error = str(exc)
            log.error("Strategy error triggered halt: %s", exc)

    def smmSchedule_timer(
        self,
        key: str,
        delay_ns: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SmmTimerToken:
        if delay_ns < 0:
            raise ValueError("delay_ns must be non-negative")
        due_ns = self.smmClock_ns + delay_ns
        token = SmmTimerToken(
            timer_id=self._next_timer_id,
            key=key,
            due_ns=due_ns,
            metadata=None if metadata is None else dict(metadata),
        )
        self._next_timer_id += 1
        heapq.heappush(self._timer_heap, (token.due_ns, token.timer_id, token))
        self._active_timers[token.timer_id] = token
        return token

    def smmCancel_timer(self, token: SmmTimerToken) -> bool:
        return self._active_timers.pop(token.timer_id, None) is not None

    def _fire_due_timers(self, current_ns: int) -> None:
        if self._sandbox is None or self.strategy_halted:
            return
        while self._timer_heap and self._timer_heap[0][0] <= current_ns:
            _, _, token = heapq.heappop(self._timer_heap)
            active = self._active_timers.pop(token.timer_id, None)
            if active is None:
                continue
            self._strategy_call("smmOn_timer", token, self._context)
            self._render_dashboard()
            if self.strategy_halted:
                break


__all__ = [
    "SmmBacktester",
    "SmmBacktesterConfig",
    "SmmOrderRequest",
    "SmmFillEvent",
    "SmmMarketEvent",
    "SmmMarketSnapshot",
    "SmmOrderBookUpdate",
    "SmmStrategyCallbacks",
    "SmmStrategyContext",
    "SmmTimerToken",
]


