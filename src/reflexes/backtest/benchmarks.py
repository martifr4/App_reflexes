"""Benchmark weight generators, run through the same engine for a fair comparison.

Both benchmarks are expressed as target-weight frames so they pass through the exact
same next-bar execution and cost model as the strategy — no benchmark gets a free pass
on costs or execution timing.
"""
from __future__ import annotations

import pandas as pd


def buy_and_hold_weights(index: pd.DatetimeIndex, assets: list[str], hold_asset: str = "BTC") -> pd.DataFrame:
    """Constant full long in ``hold_asset`` (default BTC). Near-zero turnover after entry."""
    w = pd.DataFrame(0.0, index=index, columns=assets)
    if hold_asset in w.columns:
        w[hold_asset] = 1.0
    return w


def equal_weight_weights(index: pd.DatetimeIndex, assets: list[str]) -> pd.DataFrame:
    """Equal long weight across all assets, rebalanced daily to the target."""
    n = len(assets)
    if n == 0:
        return pd.DataFrame(index=index)
    return pd.DataFrame(1.0 / n, index=index, columns=assets)
