"""Performance metrics. Crypto trades 365 days/year, so we annualize on 365.

All metrics are computed from a daily net-return series (and the matching turnover/cost
series where relevant). Nothing here peeks at the future; metrics are pure functions of
the realized return path.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ANNUAL = 365.0


def _drawdown(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return equity / peak - 1.0


def compute_metrics(returns: pd.Series, equity: pd.Series | None = None,
                    turnover: pd.Series | None = None, costs: pd.Series | None = None) -> dict:
    """Compute the standard report metrics from a daily net-return series."""
    r = returns.dropna()
    if len(r) == 0:
        return {k: np.nan for k in (
            "n_days", "cagr", "ann_return", "ann_vol", "sharpe", "sortino",
            "max_drawdown", "hit_rate", "avg_win", "avg_loss", "win_loss_ratio",
            "turnover_annual", "total_costs")}

    if equity is None:
        equity = (1.0 + r).cumprod()

    n = len(r)
    years = n / ANNUAL
    total_growth = float((1.0 + r).prod())
    cagr = total_growth ** (1.0 / years) - 1.0 if years > 0 and total_growth > 0 else np.nan

    ann_return = float(r.mean()) * ANNUAL
    ann_vol = float(r.std(ddof=0)) * np.sqrt(ANNUAL)
    sharpe = ann_return / ann_vol if ann_vol > 1e-12 else np.nan

    downside = r[r < 0]
    downside_vol = float(downside.std(ddof=0)) * np.sqrt(ANNUAL) if len(downside) > 1 else np.nan
    sortino = ann_return / downside_vol if downside_vol and downside_vol > 1e-12 else np.nan

    max_dd = float(_drawdown(equity).min())

    nonzero = r[r != 0.0]
    wins = nonzero[nonzero > 0]
    losses = nonzero[nonzero < 0]
    hit_rate = len(wins) / len(nonzero) if len(nonzero) else np.nan
    avg_win = float(wins.mean()) if len(wins) else np.nan
    avg_loss = float(losses.mean()) if len(losses) else np.nan
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss and not np.isnan(avg_loss) and avg_loss != 0 else np.nan

    turnover_annual = float(turnover.dropna().mean()) * ANNUAL if turnover is not None else np.nan
    total_costs = float(costs.dropna().sum()) if costs is not None else np.nan

    return {
        "n_days": int(n),
        "cagr": cagr,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "hit_rate": hit_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "turnover_annual": turnover_annual,
        "total_costs": total_costs,
    }


def metrics_table(named_results: dict[str, dict]) -> pd.DataFrame:
    """Turn ``{label: metrics_dict}`` into a tidy comparison table (metrics as rows)."""
    return pd.DataFrame(named_results)
