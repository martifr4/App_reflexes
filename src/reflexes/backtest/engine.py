"""Event-agnostic vectorized daily backtest with realistic, lookahead-free execution.

Execution model (the part that matters most)
--------------------------------------------
A target weight ``w_T`` is *decided at the close of bar T* using only data observed at
or before T. It is then **executed at the next bar's price** (open or close per config)
and held for one full bar:

    decide at close[T]  ->  execute at price[T+1]  ->  earn return price[T+1] -> price[T+2]

Concretely, the weight that earns the return over interval ``[k-1, k]`` is the weight
decided two bars earlier: ``held_weight = target_weight.shift(2)``. The 2-bar shift is
what guarantees we *never* trade on the same bar we decided on — there is always a full
bar between the decision (close[T]) and the start of the holding period (price[T+1]).
A naive 1-bar close-to-close lag would enter at close[T], the same bar as the decision;
that is exactly the lookahead this engine refuses to do.

Costs
-----
Trading cost and slippage are charged (in bps) on realized turnover — the change in the
held weight when a rebalance actually executes — deducted from that bar's return.

Assertions
----------
:func:`assert_no_lookahead` verifies the held-weight alignment really is ``shift(2)`` of
the target, so a refactor can't silently reintroduce same-bar execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..data.ingest import to_panel

EXECUTION_LAG_BARS = 2  # decide at close[T], hold return over [T+1 -> T+2]


@dataclass
class BacktestResult:
    equity: pd.Series               # portfolio equity curve (starts at initial_capital)
    returns: pd.Series              # daily net portfolio returns
    gross_returns: pd.Series        # daily returns before costs
    held_weights: pd.DataFrame      # weights actually held each bar (date x asset)
    turnover: pd.Series             # daily one-sided turnover (sum |Δw|)
    costs: pd.Series                # daily cost drag (fraction)
    meta: dict = field(default_factory=dict)


def _exec_price_panel(frames: dict[str, pd.DataFrame], execution: str) -> pd.DataFrame:
    field_name = "open" if execution == "next_open" else "close"
    px = to_panel(frames, field_name=field_name)
    return px.sort_index()


def assert_no_lookahead(target_weights: pd.DataFrame, held_weights: pd.DataFrame,
                        lag: int = EXECUTION_LAG_BARS) -> None:
    """Assert held weights are exactly ``target.shift(lag)`` — i.e. no same-bar execution.

    Raises AssertionError if any held weight at bar k depends on a target decided later
    than bar ``k - lag`` (which would be lookahead / same-bar trading).
    """
    expected = target_weights.reindex(held_weights.index).shift(lag)
    # Compare only where both are defined; treat NaN-vs-NaN as equal.
    a = held_weights.fillna(0.0)
    b = expected.fillna(0.0)
    if not np.allclose(a.values, b.values, atol=1e-12):
        bad = (~np.isclose(a.values, b.values, atol=1e-12)).sum()
        raise AssertionError(
            f"Lookahead check failed: held weights are not target.shift({lag}) "
            f"in {bad} cells. Execution may be using same-bar or future data."
        )


def run_backtest(frames: dict[str, pd.DataFrame], target_weights: pd.DataFrame,
                 cfg, verify: bool = True) -> BacktestResult:
    """Run the daily backtest.

    Parameters
    ----------
    frames: mapping asset -> OHLCV frame (UTC daily index).
    target_weights: date x asset target weights decided at each bar's close.
    cfg: full config (uses the ``backtest`` section).
    verify: run the no-lookahead assertion (default True).
    """
    bt = cfg["backtest"] if "backtest" in cfg else cfg
    execution = bt.get("execution", "next_open")
    cost_bps = float(bt.get("cost_bps", 10.0)) / 1e4
    slippage_bps = float(bt.get("slippage_bps", 5.0)) / 1e4
    initial_capital = float(bt.get("initial_capital", 1_000_000))

    px = _exec_price_panel(frames, execution)
    assets = list(target_weights.columns)
    px = px.reindex(columns=assets)

    # Align target weights onto the price calendar.
    tw = target_weights.reindex(px.index).reindex(columns=assets)

    # Per-bar simple returns of the execution price (interval ending at each bar).
    asset_ret = px.pct_change().fillna(0.0)

    # Held weight earning the return over [k-1, k] was decided 2 bars earlier.
    held = tw.shift(EXECUTION_LAG_BARS)
    held = held.fillna(0.0)

    if verify:
        assert_no_lookahead(tw, held)

    # Turnover at each bar = change in held weight (one-sided sum of |Δw|).
    prev = held.shift(1).fillna(0.0)
    turnover = (held - prev).abs().sum(axis=1)

    # Cost drag: (cost + slippage) bps per unit turnover, charged on the rebalance bar.
    cost_rate = cost_bps + slippage_bps
    costs = turnover * cost_rate

    gross_returns = (held * asset_ret).sum(axis=1)
    net_returns = gross_returns - costs

    equity = initial_capital * (1.0 + net_returns).cumprod()

    return BacktestResult(
        equity=equity,
        returns=net_returns,
        gross_returns=gross_returns,
        held_weights=held,
        turnover=turnover,
        costs=costs,
        meta={
            "execution": execution,
            "cost_bps": bt.get("cost_bps"),
            "slippage_bps": bt.get("slippage_bps"),
            "initial_capital": initial_capital,
            "total_costs_fraction": float(costs.sum()),
        },
    )
