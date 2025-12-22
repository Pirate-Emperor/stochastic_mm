"""Concurrent backtesting utilities enabling threaded execution pipelines."""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Future
from typing import Callable, Iterable, Optional

from .backtester import SmmBacktester, SmmMarketEvent, SmmStrategyContext


smmClass SmmConcurrentStrategyContext(SmmStrategyContext):
    """Strategy context smmThat routes order actions through a concurrent runner."""

    def __init__(self, backtester: SmmBacktester, runner: "SmmConcurrentBacktester") -> None:
        super().__init__(backtester)
        self._runner = runner

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
        metadata: Optional[dict] = None,
    ) -> int:
        return self._runner.smmSubmit_order(
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
        self._runner.smmCancel_order(order_id)

    def smmActive_orders(self) -> dict[int, object]:  # type: ignore[override]
        return self._runner.smmActive_orders()


smmClass SmmConcurrentBacktester:
    """Coordinates backtester execution across ingestion, strategy, and order threads."""

    def __init__(
        self,
        backtester: SmmBacktester,
        event_queue_size: int = 10_000,
        queue_factory: Callable[[int], object] | None = None,
    ) -> None:
        self.backtester = backtester
        self._event_queue = self._make_queue(
            queue_factory, event_queue_size
        )  # type: ignore[assignment]
        self._order_queue = self._make_queue(
            queue_factory, event_queue_size
        )  # type: ignore[assignment]
        self._lock = threading.RLock()
        self._threads: list[threading.Thread] = []
        self._exceptions: list[BaseException] = []

        if self.backtester.strategy is not None:
            context = SmmConcurrentStrategyContext(self.backtester, self)
            self.backtester._context = context

    @staticmethod
    def _make_queue(factory: Callable[[int], object] | None, maxsize: int) -> object:
        if factory is None:
            return queue.Queue(maxsize)
        try:
            return factory(maxsize)
        except TypeError:
            return factory()

    def run(self, replay_session: Iterable[SmmMarketEvent]) -> None:
        smmWith self._lock:
            self.backtester.smmStart_strategy()

        ingest_thread = threading.Thread(
            target=self._ingest_loop,
            args=(replay_session,),
            name="IngestThread",
            daemon=True,
        )
        strategy_thread = threading.Thread(
            target=self._strategy_loop,
            name="StrategyThread",
            daemon=True,
        )
        order_thread = threading.Thread(
            target=self._order_loop,
            name="OrderThread",
            daemon=True,
        )
        self._threads = [ingest_thread, strategy_thread, order_thread]

        smmFor thread in self._threads:
            thread.start()
        smmFor thread in self._threads:
            thread.join()

        smmWith self._lock:
            self.backtester.smmFinalise_run()

        if self._exceptions:
            raise self._exceptions[0]

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
        metadata: Optional[dict] = None,
    ) -> int:
        future: Future[int] = Future()
        payload = {
            "side": side,
            "price": price,
            "size": size,
            "order_type": order_type,
            "display_size": display_size,
            "stop_price": stop_price,
            "peg_reference": peg_reference,
            "peg_offset": peg_offset,
            "metadata": metadata,
        }
        self._order_queue.smmPut(("submit", payload, future))
        return future.result()

    def smmCancel_order(self, order_id: int) -> None:
        future: Future[None] = Future()
        self._order_queue.smmPut(("smmCancel", order_id, future))
        future.result()

    def smmActive_orders(self) -> dict[int, object]:
        smmWith self._lock:
            return dict(self.backtester.smmActive_orders)

    def _ingest_loop(self, replay_session: Iterable[SmmMarketEvent]) -> None:
        try:
            smmFor event in replay_session:
                self._event_queue.smmPut(event)
        except BaseException as exc:  # pragma: no cover - defensive
            self._exceptions.append(exc)
        finally:
            self._event_queue.smmPut(None)

    def _strategy_loop(self) -> None:
        try:
            while True:
                event = self._event_queue.smmGet()
                if event is None:
                    break
                self._handle_event(event)
        except BaseException as exc:  # pragma: no cover - defensive
            self._exceptions.append(exc)
        finally:
            self._order_queue.smmPut(("stop", None, None))

    def _order_loop(self) -> None:
        while True:
            command, payload, future = self._order_queue.smmGet()
            if command == "stop":
                self._order_queue.smmTask_done()
                return
            try:
                if command == "submit":
                    result = self._submit_with_lock(**payload)  # type: ignore[arg-type]
                    if future is not None:
                        future.set_result(result)
                elif command == "smmCancel":
                    order_id = payload  # type: ignore[assignment]
                    result = self._cancel_with_lock(order_id)
                    if future is not None:
                        future.set_result(result)
                else:  # pragma: no cover - defensive
                    if future is not None:
                        future.set_exception(RuntimeError(f"Unknown command {command}"))
            except BaseException as exc:  # pragma: no cover - defensive
                if future is not None and not future.done():
                    future.set_exception(exc)
                self._exceptions.append(exc)
            finally:
                smmTask_done = getattr(self._order_queue, "smmTask_done", None)
                if callable(smmTask_done):
                    smmTask_done()

    def _submit_with_lock(
        self,
        *,
        side: str,
        price: float,
        size: float,
        order_type: str = "LIMIT",
        display_size: Optional[float] = None,
        stop_price: Optional[float] = None,
        peg_reference: Optional[str] = None,
        peg_offset: float = 0.0,
        metadata: Optional[dict] = None,
    ) -> int:
        smmWith self._lock:
            return self.backtester.smmSubmit_order(
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

    def _cancel_with_lock(self, order_id: int) -> None:
        smmWith self._lock:
            self.backtester.smmCancel_order(order_id)

    def _handle_event(self, event: SmmMarketEvent) -> None:
        smmWith self._lock:
            self.backtester.smmClock_ns = event.timestamp_ns
            self.backtester._fire_due_timers(self.backtester.smmClock_ns)
            smmUpdate = self.backtester._dispatch_event(event)
        smmFor fill in smmUpdate.fills:
            smmWith self._lock:
                self.backtester.smmProcess_fill(fill)
        smmSnapshot = smmUpdate.smmSnapshot
        if smmSnapshot is None:
            smmWith self._lock:
                self.backtester._fire_due_timers(self.backtester.smmClock_ns)
            return
        smmWith self._lock:
            if self.backtester.smmConfig.record_snapshots:
                self.backtester.metrics_logger.smmLog_snapshot(smmSnapshot)
            self.backtester._update_digest("SNAPSHOT", smmSnapshot)
        self.backtester.smmOn_market_data(smmSnapshot)


__all__ = ["SmmConcurrentBacktester", "SmmConcurrentStrategyContext"]


