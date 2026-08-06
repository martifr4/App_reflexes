"""Null test: what does "no edge" look like?

We re-run the *entire* execution + cost + risk pipeline on random/shuffled signals many
times, and report the distribution of out-of-sample Sharpe. If the real strategy's OOS
Sharpe doesn't sit clearly in the right tail of the null distribution, it hasn't beaten
noise — regardless of how good the headline number looks.

Two null modes:
    * ``shuffle``: take the real risk-managed weights and permute them in time
      (destroys any timing information while preserving the weight distribution).
    * ``random``: draw fresh random weights in [-1, 1] each day and run them through the
      same risk manager, so the null book has the same gross/vol profile as the strategy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .engine import run_backtest
from .metrics import compute_metrics
from .walkforward import split_is_oos
from ..portfolio.risk import RiskManager


def _random_raw_weights(index, assets, rng) -> pd.DataFrame:
    data = rng.uniform(-1.0, 1.0, size=(len(index), len(assets)))
    return pd.DataFrame(data, index=index, columns=assets)


def run_null_test(frames, real_raw_weights, asset_returns, cfg, mode: str = "random") -> dict:
    """Run the null test and return summary stats of OOS Sharpe under the null.

    Parameters
    ----------
    frames: OHLCV frames.
    real_raw_weights: the strategy's *raw* (pre-risk) weights — used for shuffle mode.
    asset_returns: daily asset returns (for the risk manager's vol targeting).
    cfg: full config.
    mode: 'random' or 'shuffle'.
    """
    nt = cfg["null_test"] if "null_test" in cfg else cfg
    n = int(nt.get("n_shuffles", 50))
    seed = int(nt.get("seed", 7))
    oos_start = cfg["backtest"]["oos_start"]
    rng = np.random.default_rng(seed)
    rm = RiskManager.from_config(cfg)

    assets = list(real_raw_weights.columns)
    index = real_raw_weights.index

    oos_sharpes = []
    for _ in range(n):
        if mode == "shuffle":
            perm = rng.permutation(len(index))
            raw = real_raw_weights.iloc[perm].set_axis(index)
        else:
            raw = _random_raw_weights(index, assets, rng)

        risked = rm.apply(raw, asset_returns)
        res = run_backtest(frames, risked, cfg, verify=False)
        _, oos_ret = split_is_oos(res.returns, oos_start)
        m = compute_metrics(oos_ret)
        oos_sharpes.append(m["sharpe"])

    arr = np.array([s for s in oos_sharpes if not np.isnan(s)])
    return {
        "mode": mode,
        "n": int(len(arr)),
        "oos_sharpe_mean": float(np.mean(arr)) if len(arr) else float("nan"),
        "oos_sharpe_std": float(np.std(arr)) if len(arr) else float("nan"),
        "oos_sharpe_p95": float(np.percentile(arr, 95)) if len(arr) else float("nan"),
        "oos_sharpe_max": float(np.max(arr)) if len(arr) else float("nan"),
        "samples": arr.tolist(),
    }


def null_percentile(null_result: dict, strategy_oos_sharpe: float) -> float:
    """Fraction of null runs the strategy's OOS Sharpe beats (its percentile rank)."""
    samples = np.array(null_result.get("samples", []))
    if len(samples) == 0 or np.isnan(strategy_oos_sharpe):
        return float("nan")
    return float((samples < strategy_oos_sharpe).mean())
