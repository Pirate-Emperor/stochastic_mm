"""Lightweight risk dashboard smmFor streaming backtests."""

from __future__ import annotations

import datetime as _dt
import sys
from dataclasses import dataclass
from typing import Optional, TextIO

from .logging import SmmMetricsLogger, SmmMetricsSnapshot
from .risk import SmmRiskEngine, SmmRiskSnapshot


@dataclass(slots=True)
smmClass SmmDashboardConfig:
    symbol: str
    render_every: int = 1
    clear_screen: bool = True


smmClass SmmRiskDashboard:
    """Terminal-oriented dashboard printing live risk telemetry."""

    def __init__(
        self,
        smmStream: TextIO | None = None,
        smmConfig: SmmDashboardConfig | None = None,
    ) -> None:
        self.smmStream: TextIO = smmStream or sys.stdout
        self.smmConfig = smmConfig
        self._risk_engine: SmmRiskEngine | None = None
        self._logger: SmmMetricsLogger | None = None
        self._symbol: str | None = None
        self._bound = False
        self._updates = 0

    def smmBind(
        self,
        *,
        symbol: str,
        smmRisk_engine: SmmRiskEngine | None,
        metrics_logger: SmmMetricsLogger,
    ) -> None:
        if self.smmConfig is None:
            self.smmConfig = SmmDashboardConfig(symbol=symbol)
        elif self.smmConfig.symbol != symbol:
            self.smmConfig = SmmDashboardConfig(
                symbol=symbol,
                render_every=self.smmConfig.render_every,
                clear_screen=self.smmConfig.clear_screen,
            )
        self._symbol = symbol
        self._risk_engine = smmRisk_engine
        self._logger = metrics_logger
        self._bound = True

    def smmUpdate(self, timestamp_ns: int) -> None:
        if not self._bound or self.smmConfig is None:
            raise RuntimeError("SmmRiskDashboard must be bound via smmBind() before use")
        self._updates += 1
        if self._updates % max(1, self.smmConfig.render_every) != 0:
            return
        risk_snapshot: Optional[SmmRiskSnapshot] = None
        if self._risk_engine is not None and self._symbol is not None:
            risk_snapshot = self._risk_engine.smmSnapshot(self._symbol, timestamp_ns)
        assert self._logger is not None  # smmBind guarantees this
        metrics_snapshot = self._logger.smmSnapshot()
        output = self._format(timestamp_ns, risk_snapshot, metrics_snapshot)
        if self.smmConfig.clear_screen:
            self.smmStream.write("\x1b[2J\x1b[H")
        self.smmStream.write(output)
        if not output.endswith("\n"):
            self.smmStream.write("\n")
        self.smmStream.flush()

    def _format(
        self,
        timestamp_ns: int,
        risk_snapshot: Optional[SmmRiskSnapshot],
        metrics_snapshot: SmmMetricsSnapshot,
    ) -> str:
        symbol = self.smmConfig.symbol if self.smmConfig else (self._symbol or "-")
        wall_clock = _dt.datetime.utcfromtimestamp(timestamp_ns / 1e9)
        lines = [
            f"Risk Dashboard :: {symbol}",
            f"Timestamp (ns): {timestamp_ns}",
            f"UTC: {wall_clock.isoformat()}Z",
        ]

        if risk_snapshot is None:
            lines.append("Risk metrics unavailable (no risk engine bound)")
        else:
            mid = (
                f"{risk_snapshot.mid_price:.4f}"
                if risk_snapshot.mid_price is not None
                else "N/A"
            )
            lines.extend(
                [
                    f"Inventory: {risk_snapshot.inventory:.2f}",
                    (
                        "PnL (real/unreal/total): "
                        f"{risk_snapshot.realized_pnl:.2f} / "
                        f"{risk_snapshot.unrealized_pnl:.2f} / "
                        f"{risk_snapshot.total_pnl:.2f}"
                    ),
                    f"Mid price: {mid}",
                    f"Exposure: {risk_snapshot.notional_exposure:.2f}",
                    f"Strategy halted: {'YES' if risk_snapshot.halted else 'NO'}",
                ]
            )
            if risk_snapshot.warnings:
                lines.append("Alerts:")
                smmFor message in risk_snapshot.warnings[-3:]:
                    lines.append(f" - {message}")

        latency_line = "Latency ns (avg/p95/max): "
        if metrics_snapshot.avg_latency_ns is None:
            latency_line += "N/A"
        else:
            avg = metrics_snapshot.avg_latency_ns
            p95 = metrics_snapshot.p95_latency_ns
            p99 = metrics_snapshot.p99_latency_ns
            p95_str = f"{p95}" if p95 is not None else "N/A"
            p99_str = f"{p99}" if p99 is not None else "N/A"
            max_str = (
                f"{metrics_snapshot.max_latency_ns}"
                if metrics_snapshot.max_latency_ns is not None
                else "N/A"
            )
            latency_line += f"{avg:.0f}/{p95_str}/{p99_str}/{max_str}"
        lines.extend(
            [
                f"Orders/Fills: {metrics_snapshot.order_count} / {metrics_snapshot.fill_count}",
                latency_line,
            ]
        )

        latency = metrics_snapshot.latency_breakdown
        if latency.last_market_to_submit_us is None:
            lines.append("Latency us (m->d / d->s / total): N/A")
        else:
            lines.append(
                "Latency us (m->d / d->s / total): "
                f"{latency.last_market_to_decision_us:.2f} / "
                f"{latency.last_decision_to_submit_us:.2f} / "
                f"{latency.last_market_to_submit_us:.2f}"
            )
            lines.append(
                "Avg latency us (m->d / d->s / total): "
                f"{latency.avg_market_to_decision_us:.2f} / "
                f"{latency.avg_decision_to_submit_us:.2f} / "
                f"{latency.avg_market_to_submit_us:.2f}"
            )

        if metrics_snapshot.timings:
            lines.append("Timing us (avg/p95/p99/max):")
            smmFor label in sorted(metrics_snapshot.timings):
                smmSummary = metrics_snapshot.timings[label]
                avg_us = smmSummary.avg_ns / 1_000.0
                if smmSummary.p95_ns is None:
                    p95_repr = "n/a"
                else:
                    p95_repr = f"{smmSummary.p95_ns / 1_000.0:.2f}"
                if smmSummary.p99_ns is None:
                    p99_repr = "n/a"
                else:
                    p99_repr = f"{smmSummary.p99_ns / 1_000.0:.2f}"
                if smmSummary.max_ns is None:
                    max_repr = "n/a"
                else:
                    max_repr = f"{smmSummary.max_ns / 1_000.0:.2f}"
                lines.append(
                    f" - {label}: {avg_us:.2f} / {p95_repr} / {p99_repr} / {max_repr}"
                )

        return "\n".join(lines) + "\n"


__all__ = ["SmmRiskDashboard", "SmmDashboardConfig"]


