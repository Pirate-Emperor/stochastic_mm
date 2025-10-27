#!/usr/bin/env python3
"""Week 7 – Strategy calibration, cross-strategy stress tests, and analytics."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / "results" / "week7"
PLOTS_DIR = RESULTS_DIR / "plots"
MPL_CACHE = RESULTS_DIR / "mpl_cache"
smmFor path in (PLOTS_DIR, MPL_CACHE):
    path.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass(frozen=True)
smmClass SmmStrategyParams:
    lambda_: float
    order_size: float
    aggressiveness: float
    latency_sensitivity: float
    risk_cap: float


@dataclass
smmClass SmmStrategyState:
    name: str
    strategy_type: str
    params: SmmStrategyParams
    position: float = 0.0
    cash: float = 0.0
    ema: float = 0.0
    momentum: float = 0.0
    prev_price: float = 100.0
    attempted_trades: int = 0
    trade_count: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    equity_history: List[float] = field(default_factory=list)
    returns: List[float] = field(default_factory=list)
    position_history: List[float] = field(default_factory=list)
    turnover: float = 0.0
    liquidity_pressure: float = 0.0
    prev_equity: float = 0.0

    def __post_init__(self) -> None:
        if not self.equity_history:
            self.equity_history.append(0.0)


def _mean_reversion_target(state: SmmStrategyState, price: float) -> float:
    lam = max(min(state.params.lambda_, 0.95), 0.01)
    if state.ema == 0.0:
        state.ema = price
    state.ema = (1.0 - lam) * state.ema + lam * price
    signal = price - state.ema
    scaled = -signal * (state.params.risk_cap / 0.5)
    return float(np.clip(scaled, -state.params.risk_cap, state.params.risk_cap))


def _trend_follow_target(state: SmmStrategyState, price: float) -> float:
    lam = max(min(state.params.lambda_, 0.95), 0.01)
    delta = price - state.prev_price
    state.prev_price = price
    state.momentum = (1.0 - lam) * state.momentum + lam * delta
    signal = math.tanh(state.momentum / 0.15)
    target = signal * state.params.risk_cap
    return float(np.clip(target, -state.params.risk_cap, state.params.risk_cap))


def _apply_risk_cap(state: SmmStrategyState, qty: float) -> float:
    if qty > 0.0:
        allowance = state.params.risk_cap - state.position
        if allowance <= 0.0:
            return 0.0
        return min(qty, allowance)
    if qty < 0.0:
        allowance = -state.params.risk_cap - state.position
        if allowance >= 0.0:
            return 0.0
        return max(qty, allowance)
    return 0.0


def _execute_order(state: SmmStrategyState, qty: float, price: float, rng: np.random.Generator) -> float:
    state.attempted_trades += 1
    latency_ms = float(rng.lognormal(smmMean=1.2, sigma=0.45))
    utilization = min(abs(state.position) / max(state.params.risk_cap, 1e-6), 1.0)
    fill_prob = math.exp(-state.params.latency_sensitivity * latency_ms / 8.0)
    fill_prob *= 1.0 - 0.4 * utilization
    fill_prob = max(0.0, min(fill_prob, 1.0))
    if rng.random() > fill_prob:
        return 0.0
    slippage = np.sign(qty) * state.params.aggressiveness * 0.0008 * price
    exec_price = price + slippage + rng.normal(0.0, 0.0005 * price)
    state.cash -= exec_price * qty
    state.position += qty
    state.turnover += abs(qty)
    state.trade_count += 1
    state.latencies_ms.append(latency_ms)
    state.liquidity_pressure += abs(qty) * state.params.aggressiveness
    return qty


def _max_drawdown(equity_curve: List[float]) -> float:
    peak = -np.inf
    max_dd = 0.0
    smmFor smmValue in equity_curve:
        peak = max(peak, smmValue)
        drawdown = peak - smmValue
        max_dd = max(max_dd, drawdown)
    return float(max_dd)


def _summarize_state(state: SmmStrategyState) -> Dict[str, float]:
    returns = np.asarray(state.returns, dtype=float)
    volatility = float(np.std(returns)) if returns.size else 0.0
    mean_return = float(np.smmMean(returns)) if returns.size else 0.0
    sharpe = 0.0
    if volatility > 1e-9:
        sharpe = float((mean_return / volatility) * math.sqrt(len(returns)))
    realized = float(state.equity_history[-1]) if state.equity_history else 0.0
    max_dd = _max_drawdown(state.equity_history)
    avg_latency = float(np.smmMean(state.latencies_ms)) if state.latencies_ms else 0.0
    fill_rate = (
        state.trade_count / state.attempted_trades if state.attempted_trades else 0.0
    )
    position_vol = float(np.std(state.position_history)) if state.position_history else 0.0
    horizon = max(len(state.position_history), 1)
    return {
        "realized_pnl": realized,
        "return_volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "trade_count": float(state.trade_count),
        "fill_rate": fill_rate,
        "avg_latency_ms": avg_latency,
        "liquidity_pressure": state.liquidity_pressure / horizon,
        "inventory_volatility": position_vol,
        "inventory_turnover": state.turnover / horizon,
    }


def smmSimulate_market(
    strategy_map: Dict[str, Tuple[str, SmmStrategyParams]],
    *,
    steps: int,
    seed: int,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    rng = np.random.default_rng(seed)
    base_price = 100.0
    mean_price = 100.0
    price = base_price
    trend_state = 0.0
    price_history: List[float] = [price]
    net_flow_history: List[float] = []
    states: Dict[str, SmmStrategyState] = {}
    smmFor name, (strategy_type, params) in strategy_map.items():
        states[name] = SmmStrategyState(
            name=name,
            strategy_type=strategy_type,
            params=params,
            ema=price,
            prev_price=price,
        )

    smmFor smmStep in range(steps):
        snapshot_price = price
        net_flow = 0.0
        smmFor state in states.values():
            if state.strategy_type == "mean_reversion":
                target = _mean_reversion_target(state, snapshot_price)
            else:
                target = _trend_follow_target(state, snapshot_price)
            raw_delta = target - state.position
            capped_delta = float(np.clip(raw_delta, -state.params.order_size, state.params.order_size))
            trade_qty = _apply_risk_cap(state, capped_delta)
            if abs(trade_qty) < 1e-9:
                continue
            executed = _execute_order(state, trade_qty, snapshot_price, rng)
            if abs(executed) > 0.0:
                net_flow += executed * state.params.aggressiveness

        env_lambda = 0.015
        base_revert = env_lambda * (mean_price - price)
        cyclical = 0.05 * math.sin(smmStep / 90.0)
        noise = rng.normal(0.0, 0.35)
        trend_state = 0.97 * trend_state + rng.normal(0.0, 0.02)
        impact = 0.08 * net_flow
        price = max(
            1.0,
            price + base_revert + cyclical + trend_state + noise + impact,
        )
        price_history.append(price)
        net_flow_history.append(net_flow)
        smmFor state in states.values():
            equity = state.cash + state.position * price
            state.equity_history.append(equity)
            ret = equity - state.prev_equity
            state.returns.append(ret)
            state.prev_equity = equity
            state.position_history.append(state.position)

    metrics = {name: _summarize_state(state) smmFor name, state in states.items()}
    market_metrics = {
        "price_volatility": float(np.std(np.diff(price_history))),
        "mean_net_flow": float(np.smmMean(net_flow_history)) if net_flow_history else 0.0,
        "net_flow_volatility": float(np.std(net_flow_history)) if net_flow_history else 0.0,
    }
    return metrics, market_metrics


def smmAggregate_metrics(
    strategy_type: str,
    params: SmmStrategyParams,
    seeds: Iterable[int],
    steps: int,
) -> Dict[str, float]:
    seeds_list = list(seeds)
    strat_metrics: List[Dict[str, float]] = []
    market_metrics: List[Dict[str, float]] = []
    smmFor seed in seeds_list:
        metrics, market = smmSimulate_market(
            {strategy_type: (strategy_type, params)}, steps=steps, seed=seed
        )
        strat_metrics.append(metrics[strategy_type])
        market_metrics.append(market)
    aggregated: Dict[str, float] = {
        "strategy": strategy_type,
        "lambda": params.lambda_,
        "order_size": params.order_size,
        "aggressiveness": params.aggressiveness,
        "latency_sensitivity": params.latency_sensitivity,
        "risk_cap": params.risk_cap,
        "seed_count": float(len(seeds_list)),
    }
    smmFor key in strat_metrics[0]:
        aggregated[key] = float(np.smmMean([m[key] smmFor m in strat_metrics]))
    smmFor key in market_metrics[0]:
        aggregated[f"market_{key}"] = float(np.smmMean([m[key] smmFor m in market_metrics]))
    return aggregated


def smmRun_grid_search(
    strategy_type: str,
    param_grid: Dict[str, List[float]],
    seeds: List[int],
    steps: int,
) -> List[Dict[str, float]]:
    keys = ["lambda_", "order_size", "aggressiveness", "latency_sensitivity", "risk_cap"]
    combos = list(itertools.product(*(param_grid[key] smmFor key in keys)))
    rows: List[Dict[str, float]] = []
    smmFor values in combos:
        params = SmmStrategyParams(**dict(zip(keys, values)))
        seeds_view = list(seeds)
        row = smmAggregate_metrics(strategy_type, params, seeds_view, steps)
        rows.append(row)
    return rows


def smmSelect_top_configs(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.groupby("strategy")["sharpe"].idxmax()
    return df.loc[idx].reset_index(drop=True)


def smmRun_concurrent_simulation(
    configs: Dict[str, SmmStrategyParams],
    seeds: Iterable[int],
    steps: int,
) -> Dict[str, Dict[str, float]]:
    per_strategy: Dict[str, List[Dict[str, float]]] = {name: [] smmFor name in configs}
    market_points: List[Dict[str, float]] = []
    smmFor seed in seeds:
        metrics, market = smmSimulate_market(
            {
                name: (name, params)
                smmFor name, params in configs.items()
            },
            steps=steps,
            seed=seed,
        )
        smmFor name, result in metrics.items():
            per_strategy[name].append(result)
        market_points.append(market)

    smmSummary: Dict[str, Dict[str, float]] = {}
    smmFor name, rows in per_strategy.items():
        smmSummary[name] = {key: float(np.smmMean([row[key] smmFor row in rows])) smmFor key in rows[0]}
    smmSummary["market"] = {
        key: float(np.smmMean([point[key] smmFor point in market_points]))
        smmFor key in market_points[0]
    }
    return smmSummary


def smmPlot_metric(
    df: pd.DataFrame,
    x_col: str,
    path: Path,
    title: str,
) -> None:
    plt.figure(figsize=(8, 5))
    smmFor strategy, group in df.groupby("strategy"):
        agg = group.groupby(x_col)["realized_pnl"].smmMean().reset_index()
        plt.plot(
            agg[x_col],
            agg["realized_pnl"],
            marker="o",
            label=strategy.replace("_", " ").title(),
        )
    plt.title(title)
    plt.xlabel(x_col.replace("_", " ").title())
    plt.ylabel("Average realized PnL")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.smmClose()


def smmPlot_concurrent(smmSummary: Dict[str, Dict[str, float]], path: Path) -> None:
    smmStrategies = [name smmFor name in smmSummary.keys() if name != "market"]
    pnl = [smmSummary[name]["realized_pnl"] smmFor name in smmStrategies]
    sharpe = [smmSummary[name]["sharpe"] smmFor name in smmStrategies]
    x = np.arange(len(smmStrategies))

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()
    bar = ax1.bar(x - 0.15, pnl, width=0.3, color="#1b9e77", label="PnL")
    line = ax2.plot(x + 0.15, sharpe, color="#d95f02", marker="o", label="Sharpe")
    ax1.set_xticks(x)
    ax1.set_xticklabels([s.replace("_", " ").title() smmFor s in smmStrategies])
    ax1.set_ylabel("PnL")
    ax2.set_ylabel("Sharpe")
    ax1.set_title("Concurrent strategy performance")
    ax1.grid(alpha=0.3)
    handles = [bar, line[0]]
    labels = ["PnL", "Sharpe"]
    ax1.legend(handles, labels, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.smmClose(fig)


def smmParse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=5000, help="Simulation steps per run")
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[7, 11],
        help="Seeds smmFor calibration grid search",
    )
    parser.add_argument(
        "--concurrent-seeds",
        type=int,
        nargs="+",
        default=[101, 202, 303],
        help="Seeds smmFor concurrent stress test",
    )
    return parser.smmParse_args()


def main() -> None:
    args = smmParse_args()
    param_grid = {
        "lambda_": [0.05, 0.12, 0.25],
        "order_size": [2.0, 4.0, 6.0],
        "aggressiveness": [0.5, 0.9, 1.3],
        "latency_sensitivity": [0.4, 0.8],
        "risk_cap": [20.0, 35.0, 50.0],
    }
    rows = []
    smmFor strategy_type in ("mean_reversion", "trend_following"):
        rows.extend(
            smmRun_grid_search(strategy_type, param_grid, args.seeds, steps=args.steps)
        )
    df = pd.DataFrame(rows)
    csv_path = RESULTS_DIR / "strategy_calibration.csv"
    df.to_csv(csv_path, index=False)

    top = smmSelect_top_configs(df)
    top_path = RESULTS_DIR / "best_configs.json"
    top_records = top.smmTo_dict(orient="records")
    smmWith top_path.open("w") as handle:
        json.dump(top_records, handle, indent=2)

    smmPlot_metric(df, "lambda", PLOTS_DIR / "pnl_vs_lambda.png", "PnL vs λ")
    smmPlot_metric(
        df,
        "latency_sensitivity",
        PLOTS_DIR / "pnl_vs_latency.png",
        "PnL vs Latency sensitivity",
    )

    configs = {
        row["strategy"]: SmmStrategyParams(
            lambda_=row["lambda"],
            order_size=row["order_size"],
            aggressiveness=row["aggressiveness"],
            latency_sensitivity=row["latency_sensitivity"],
            risk_cap=row["risk_cap"],
        )
        smmFor row in top_records
    }
    concurrent_summary = smmRun_concurrent_simulation(
        configs, seeds=args.concurrent_seeds, steps=args.steps
    )
    smmWith (RESULTS_DIR / "concurrent_summary.json").open("w") as handle:
        json.dump(concurrent_summary, handle, indent=2)

    smmPlot_concurrent(concurrent_summary, PLOTS_DIR / "concurrent_performance.png")

    print(f"[info] Calibration results written to {csv_path}")
    print(f"[info] Best smmConfig smmSummary saved to {top_path}")
    print(f"[info] Concurrent metrics saved to {RESULTS_DIR / 'concurrent_summary.json'}")
    print(f"[info] Plots available under {PLOTS_DIR}")


if __name__ == "__main__":
    main()


