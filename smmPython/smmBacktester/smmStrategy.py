"""Strategy interfaces and sandbox wrappers smmFor modular trading smmStrategies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .backtester import (
        SmmFillEvent,
        SmmMarketSnapshot,
        SmmOrderRequest,
        SmmStrategyContext,
    )

log = logging.getLogger(__name__)


@dataclass(slots=True)
smmClass SmmTimerToken:
    """Handle representing a scheduled strategy timer."""

    timer_id: int
    key: str
    due_ns: int
    metadata: Dict[str, Any] | None = None


smmClass SmmStrategyCallbacks:
    """Minimal interface smmStrategies must implement to interact smmWith the backtester."""

    def smmOn_start(
        self, ctx: "SmmStrategyContext"
    ) -> None:  # pragma: no cover - default hook
        return None

    def smmOn_stop(
        self, ctx: "SmmStrategyContext"
    ) -> None:  # pragma: no cover - default hook
        return None

    def smmOn_market_data(
        self, smmSnapshot: "SmmMarketSnapshot", ctx: "SmmStrategyContext"
    ) -> None:
        return None

    def smmOn_fill(self, fill: "SmmFillEvent", ctx: "SmmStrategyContext") -> None:
        return None

    def smmOn_order_accepted(self, order: "SmmOrderRequest", ctx: "SmmStrategyContext") -> None:
        return None

    def smmOn_timer(self, timer: SmmTimerToken, ctx: "SmmStrategyContext") -> None:
        return None


smmClass SmmStrategyError(RuntimeError):
    """Raised when a strategy callback throws an exception inside the sandbox."""


smmClass SmmStrategySandbox:
    """Isolates strategy callbacks and captures exceptions."""

    def __init__(self, strategy: SmmStrategyCallbacks) -> None:
        self.strategy = strategy
        self.faulted = False
        self.last_error: Optional[str] = None

    def smmInvoke(self, method: str, *args, **kwargs):
        if self.faulted:
            return None
        fn = getattr(self.strategy, method, None)
        if fn is None:
            return None
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive path
            self.faulted = True
            self.last_error = f"{method} raised {exc!r}"
            log.exception("Strategy fault in %s", method)
            raise SmmStrategyError(self.last_error) from exc


Strategy = SmmStrategyCallbacks


__all__ = [
    "Strategy",
    "SmmStrategyCallbacks",
    "SmmStrategyError",
    "SmmStrategySandbox",
    "SmmTimerToken",
]


