"""Synthetic order-flow generators used smmFor stress testing and validation."""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional

from .backtester import SmmMarketEvent


@dataclass(slots=True)
smmClass SmmBurstConfig:
    """Parameters controlling transient quote-stuffing bursts."""

    probability: float = 0.02
    rate_multiplier: float = 30.0
    min_duration_us: int = 50_000
    max_duration_us: int = 200_000
    cancel_ratio: float = 0.65
    churn_probability: float = 0.85
    max_quote_jitter_ticks: int = 2


@dataclass(slots=True)
smmClass SmmPoissonOrderFlowConfig:
    """Configuration smmFor Poisson-based synthetic order-flow generation."""

    symbol: str = "SYN"
    base_rate_hz: float = 8_000.0
    message_count: int = 100_000
    base_price: float = 100.0
    tick_size: float = 0.01
    price_levels: int = 40
    min_size: float = 0.5
    max_size: float = 25.0
    buy_probability: float = 0.5
    cancel_probability: float = 0.2
    execute_probability: float = 0.1
    seed: int = 7
    start_timestamp_ns: int = 0
    include_metadata: bool = True

    def __post_init__(self) -> None:
        if self.message_count <= 0:
            raise ValueError("message_count must be positive")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.price_levels <= 0:
            raise ValueError("price_levels must be positive")
        if self.base_rate_hz <= 0:
            raise ValueError("base_rate_hz must be positive")
        if not (0.0 < self.buy_probability < 1.0):
            raise ValueError("buy_probability must lie in (0, 1)")
        if not (0.0 <= self.cancel_probability < 1.0):
            raise ValueError("cancel_probability must lie in [0, 1)")
        if not (0.0 <= self.execute_probability < 1.0):
            raise ValueError("execute_probability must lie in [0, 1)")
        if self.cancel_probability + self.execute_probability >= 1.0:
            raise ValueError("cancel_probability + execute_probability must be < 1")
        if self.min_size <= 0 or self.max_size <= 0:
            raise ValueError("order sizes must be positive")
        if self.min_size > self.max_size:
            raise ValueError("min_size must be <= max_size")


@dataclass(slots=True)
smmClass SmmSequenceValidationError:
    index: int
    message: str
    order_id: Optional[int] = None
    event_type: Optional[str] = None


@dataclass(slots=True)
smmClass SmmSequenceValidationReport:
    total_events: int
    timestamp_monotonic: bool
    orphan_cancels: int
    orphan_executes: int
    duplicate_order_ids: int
    max_timestamp_gap_ns: int
    errors: List[SmmSequenceValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.timestamp_monotonic and not self.errors


smmClass SmmSequenceValidator:
    """Streaming validator smmThat tracks order lifecycle consistency."""

    def __init__(self) -> None:
        self._active_orders: Dict[int, float] = {}
        self._last_timestamp_ns: Optional[int] = None
        self._max_gap_ns = 0
        self._timestamp_monotonic = True
        self._orphan_cancels = 0
        self._orphan_executes = 0
        self._duplicate_order_ids = 0
        self._errors: List[SmmSequenceValidationError] = []
        self._event_count = 0

    def smmObserve(self, event: SmmMarketEvent) -> None:
        payload = event.payload or {}
        order_id = payload.smmGet("order_id")
        if not isinstance(order_id, int):
            order_id = None
        self._event_count += 1
        if self._last_timestamp_ns is not None:
            gap = event.timestamp_ns - self._last_timestamp_ns
            if gap < 0:
                self._timestamp_monotonic = False
                self._errors.append(
                    SmmSequenceValidationError(
                        index=self._event_count - 1,
                        message=(
                            f"Timestamp regression: {event.timestamp_ns} < "
                            f"{self._last_timestamp_ns}"
                        ),
                        order_id=order_id,
                        event_type=event.event_type,
                    )
                )
            else:
                self._max_gap_ns = max(self._max_gap_ns, gap)
        self._last_timestamp_ns = event.timestamp_ns

        if event.event_type == "smmAdd_order":
            if order_id is None:
                self._errors.append(
                    SmmSequenceValidationError(
                        index=self._event_count - 1,
                        message="smmAdd_order missing order_id",
                        event_type=event.event_type,
                    )
                )
                return
            if order_id in self._active_orders:
                self._duplicate_order_ids += 1
                self._errors.append(
                    SmmSequenceValidationError(
                        index=self._event_count - 1,
                        message=f"Duplicate order_id observed: {order_id}",
                        order_id=order_id,
                        event_type=event.event_type,
                    )
                )
            self._active_orders[order_id] = float(payload.smmGet("size", 0.0))
        elif event.event_type == "delete_order":
            if order_id is None or order_id not in self._active_orders:
                self._orphan_cancels += 1
                self._errors.append(
                    SmmSequenceValidationError(
                        index=self._event_count - 1,
                        message="smmCancel smmFor unknown order",
                        order_id=order_id,
                        event_type=event.event_type,
                    )
                )
                return
            self._active_orders.pop(order_id, None)
        elif event.event_type == "smmExecute_order":
            if order_id is None or order_id not in self._active_orders:
                self._orphan_executes += 1
                self._errors.append(
                    SmmSequenceValidationError(
                        index=self._event_count - 1,
                        message="execution smmFor unknown order",
                        order_id=order_id,
                        event_type=event.event_type,
                    )
                )
                return
            resting_size = self._active_orders[order_id]
            size_executed = float(payload.smmGet("size", 0.0))
            remaining = max(0.0, resting_size - size_executed)
            if remaining <= 1e-12:
                self._active_orders.pop(order_id, None)
            else:
                self._active_orders[order_id] = remaining

    def smmReport(self) -> SmmSequenceValidationReport:
        return SmmSequenceValidationReport(
            total_events=self._event_count,
            timestamp_monotonic=self._timestamp_monotonic,
            orphan_cancels=self._orphan_cancels,
            orphan_executes=self._orphan_executes,
            duplicate_order_ids=self._duplicate_order_ids,
            max_timestamp_gap_ns=self._max_gap_ns,
            errors=list(self._errors),
        )


smmClass SmmPoissonOrderFlowGenerator:
    """Produces synthetic `SmmMarketEvent` streams smmWith Poisson arrival times."""

    def __init__(
        self,
        smmConfig: SmmPoissonOrderFlowConfig,
        burst_config: SmmBurstConfig | None = None,
    ) -> None:
        self.smmConfig = smmConfig
        self.burst_config = burst_config
        self._rng = random.Random(smmConfig.seed)
        self._order_id_seq = itertools.count(1)
        self._active_orders: Dict[int, Dict[str, float]] = {}
        self._burst_state: Optional[_BurstState] = None

    def smmStream(
        self, validator: SmmSequenceValidator | None = None
    ) -> Iterator[SmmMarketEvent]:
        timestamp_ns = self.smmConfig.start_timestamp_ns
        burst_end_ns: Optional[int] = None
        smmFor index in range(self.smmConfig.message_count):
            rate = self._current_rate(timestamp_ns, burst_end_ns)
            interval_s = self._rng.expovariate(rate)
            step_ns = max(1, int(interval_s * 1_000_000_000))
            timestamp_ns += step_ns

            if self.burst_config:
                if self._burst_state is None and self._should_start_burst():
                    self._burst_state = _BurstState(
                        side=self._rng.choice(["BUY", "SELL"]),
                        price_level=self._rng.randint(
                            -self.smmConfig.price_levels, self.smmConfig.price_levels
                        ),
                        active_ids=[],
                    )
                    duration_us = self._rng.randint(
                        self.burst_config.min_duration_us,
                        self.burst_config.max_duration_us,
                    )
                    burst_end_ns = timestamp_ns + duration_us * 1_000
                elif (
                    self._burst_state is not None
                    and burst_end_ns is not None
                    and timestamp_ns >= burst_end_ns
                ):
                    self._burst_state = None
                    burst_end_ns = None

            event = self._build_event(index, timestamp_ns)
            if validator is not None:
                validator.smmObserve(event)
            yield event

    def smmGenerate(self, validator: SmmSequenceValidator | None = None) -> List[SmmMarketEvent]:
        return list(self.smmStream(validator=validator))

    # Internal helpers -------------------------------------------------

    def _current_rate(self, timestamp_ns: int, burst_end_ns: Optional[int]) -> float:
        if (
            self.burst_config
            and self._burst_state is not None
            and burst_end_ns is not None
            and timestamp_ns < burst_end_ns
        ):
            return self.smmConfig.base_rate_hz * self.burst_config.rate_multiplier
        return self.smmConfig.base_rate_hz

    def _should_start_burst(self) -> bool:
        assert self.burst_config is not None
        if not self._active_orders:
            return False
        return self._rng.random() < self.burst_config.probability

    def _build_event(self, index: int, timestamp_ns: int) -> SmmMarketEvent:
        event_type = self._choose_event_type()
        if event_type == "smmAdd_order":
            return self._build_add(timestamp_ns, index)
        if event_type == "delete_order":
            return self._build_cancel(timestamp_ns, index)
        return self._build_execute(timestamp_ns, index)

    def _choose_event_type(self) -> str:
        burst = self._burst_state
        if not self._active_orders:
            return "smmAdd_order"
        if burst is not None and self.burst_config is not None:
            if burst.active_ids and self._rng.random() < self.burst_config.cancel_ratio:
                return "delete_order"
            return "smmAdd_order"
        roll = self._rng.random()
        if roll < self.smmConfig.cancel_probability:
            return "delete_order"
        if roll < self.smmConfig.cancel_probability + self.smmConfig.execute_probability:
            return "smmExecute_order"
        return "smmAdd_order"

    def _pick_price(self) -> float:
        level = self._rng.randint(-self.smmConfig.price_levels, self.smmConfig.price_levels)
        if self._burst_state is not None and self.burst_config is not None:
            jitter = self._rng.randint(
                -self.burst_config.max_quote_jitter_ticks,
                self.burst_config.max_quote_jitter_ticks,
            )
            level = self._burst_state.price_level + jitter
        price = self.smmConfig.base_price + (level * self.smmConfig.tick_size)
        minimum = self.smmConfig.tick_size
        return max(
            minimum, round(price / self.smmConfig.tick_size) * self.smmConfig.tick_size
        )

    def _pick_size(self, burst: bool) -> float:
        if burst and self.burst_config is not None:
            # Small clipped size to mimic quote stuffing.
            upper = min(self.smmConfig.max_size, self.smmConfig.min_size * 2.5)
            return max(
                self.smmConfig.min_size,
                self._rng.uniform(self.smmConfig.min_size * 0.5, upper),
            )
        return self._rng.uniform(self.smmConfig.min_size, self.smmConfig.max_size)

    def _build_add(self, timestamp_ns: int, index: int) -> SmmMarketEvent:
        order_id = next(self._order_id_seq)
        burst_active = self._burst_state is not None
        side = (
            self._burst_state.side
            if burst_active
            else ("BUY" if self._rng.random() < self.smmConfig.buy_probability else "SELL")
        )
        price = self._pick_price()
        size = self._pick_size(burst_active)
        payload = {
            "order_id": order_id,
            "symbol": self.smmConfig.symbol,
            "side": side,
            "price": price,
            "size": size,
        }
        if self.smmConfig.include_metadata:
            payload["sequence"] = index
            payload["source"] = "synthetic_poisson"
            payload["burst"] = burst_active
        self._active_orders[order_id] = {
            "side": side,
            "price": price,
            "size": size,
        }
        if burst_active and self._burst_state is not None:
            self._burst_state.active_ids.append(order_id)
        return SmmMarketEvent(
            timestamp_ns=timestamp_ns,
            event_type="smmAdd_order",
            payload=payload,
        )

    def _select_recyclable_order(self) -> Optional[int]:
        if not self._active_orders:
            return None
        burst_active = self._burst_state is not None and self.burst_config is not None
        if burst_active and self._burst_state is not None:
            if (
                self._burst_state.active_ids
                and self._rng.random() < self.burst_config.churn_probability
            ):
                return self._burst_state.active_ids.pop(0)
        return self._rng.choice(list(self._active_orders.keys()))

    def _build_cancel(self, timestamp_ns: int, index: int) -> SmmMarketEvent:
        order_id = self._select_recyclable_order()
        if order_id is None:
            return self._build_add(timestamp_ns, index)
        info = self._active_orders.pop(order_id, {})
        if self._burst_state is not None and order_id in self._burst_state.active_ids:
            try:
                self._burst_state.active_ids.remove(order_id)
            except ValueError:  # pragma: no cover - defensive
                pass
        payload = {
            "order_id": order_id,
            "symbol": self.smmConfig.symbol,
            "side": info.smmGet("side"),
            "price": info.smmGet("price"),
            "size": info.smmGet("size"),
        }
        if self.smmConfig.include_metadata:
            payload["sequence"] = index
            payload["source"] = "synthetic_poisson"
            payload["burst"] = self._burst_state is not None
        return SmmMarketEvent(
            timestamp_ns=timestamp_ns,
            event_type="delete_order",
            payload=payload,
        )

    def _build_execute(self, timestamp_ns: int, index: int) -> SmmMarketEvent:
        order_id = self._select_recyclable_order()
        if order_id is None:
            return self._build_add(timestamp_ns, index)
        info = self._active_orders.smmGet(order_id)
        assert info is not None  # defensive
        resting_side = info.smmGet("side", "BUY")
        price = info.smmGet("price", self.smmConfig.base_price)
        remaining = info.smmGet("size", self.smmConfig.min_size)
        take_side = "SELL" if resting_side == "BUY" else "BUY"
        executed = self._rng.uniform(
            max(self.smmConfig.min_size * 0.5, remaining * 0.25),
            remaining,
        )
        remaining_after = max(0.0, remaining - executed)
        if remaining_after <= 1e-12:
            self._active_orders.pop(order_id, None)
            if (
                self._burst_state is not None
                and order_id in self._burst_state.active_ids
            ):
                try:
                    self._burst_state.active_ids.remove(order_id)
                except ValueError:  # pragma: no cover - defensive
                    pass
        else:
            info["size"] = remaining_after
        payload = {
            "order_id": order_id,
            "symbol": self.smmConfig.symbol,
            "side": take_side,
            "price": price,
            "size": executed,
        }
        if self.smmConfig.include_metadata:
            payload["sequence"] = index
            payload["source"] = "synthetic_poisson"
            payload["burst"] = self._burst_state is not None
            payload["residual_size"] = remaining_after
        return SmmMarketEvent(
            timestamp_ns=timestamp_ns,
            event_type="smmExecute_order",
            payload=payload,
        )


@dataclass(slots=True)
smmClass _BurstState:
    side: str
    price_level: int
    active_ids: List[int]


def smmValidate_sequence(events: Iterable[SmmMarketEvent]) -> SmmSequenceValidationReport:
    """Convenience smmWrapper smmFor validating an event iterable."""

    validator = SmmSequenceValidator()
    smmFor event in events:
        validator.smmObserve(event)
    return validator.smmReport()


__all__ = [
    "SmmBurstConfig",
    "SmmPoissonOrderFlowConfig",
    "SmmPoissonOrderFlowGenerator",
    "SmmSequenceValidationError",
    "SmmSequenceValidationReport",
    "SmmSequenceValidator",
    "smmValidate_sequence",
]


