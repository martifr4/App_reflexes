"""Portfolio construction and risk limits.

Takes raw target weights (date x asset, each in [-1, 1]) from a combiner and turns them
into risk-managed target weights, applying — in order:

    1. Per-asset concentration cap (``max_position``): no single asset beyond the cap.
    2. Gross normalization: scale so sum(|w|) equals the configured ``gross_leverage``
       (only when the raw gross exceeds it — we never lever *up* a quiet book).
    3. Volatility targeting: scale the whole book so its ex-ante annualized volatility
       matches ``vol_target_annual``. The vol estimate at date T uses the weights chosen
       at T applied to trailing asset returns observed at or before T — strictly causal.
    4. Hard gross cap (``max_gross``): clip total gross after vol scaling.

All steps at date T use only information available at T. The backtest still executes at
T+1, so there is no same-bar leakage.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 365.0  # crypto trades every day


@dataclass
class RiskManager:
    max_position: float
    gross_leverage: float
    vol_target_annual: float
    vol_target_window: int
    max_gross: float

    @classmethod
    def from_config(cls, cfg) -> "RiskManager":
        p = cfg["portfolio"] if "portfolio" in cfg else cfg
        return cls(
            max_position=float(p["max_position"]),
            gross_leverage=float(p["gross_leverage"]),
            vol_target_annual=float(p["vol_target_annual"]),
            vol_target_window=int(p["vol_target_window"]),
            max_gross=float(p["max_gross"]),
        )

    def _ex_ante_vol(self, weights_row: pd.Series, ret_window: pd.DataFrame) -> float:
        """Annualized vol of the current weights applied to trailing asset returns."""
        aligned = ret_window.reindex(columns=weights_row.index).fillna(0.0)
        port_ret = aligned.mul(weights_row, axis=1).sum(axis=1)
        daily_vol = float(port_ret.std(ddof=0))
        return daily_vol * np.sqrt(TRADING_DAYS)

    def apply(self, raw_weights: pd.DataFrame, asset_returns: pd.DataFrame) -> pd.DataFrame:
        """Return risk-managed target weights on the same index as ``raw_weights``.

        Parameters
        ----------
        raw_weights: date x asset target weights in [-1, 1] from a combiner.
        asset_returns: date x asset daily simple returns (used causally for vol target).
        """
        w = raw_weights.copy()

        # 1. Per-asset concentration cap.
        w = w.clip(lower=-self.max_position, upper=self.max_position)

        out = pd.DataFrame(index=w.index, columns=w.columns, dtype=float)
        returns = asset_returns.reindex(index=w.index)

        for T in w.index:
            row = w.loc[T].fillna(0.0)
            gross = row.abs().sum()
            if gross <= 1e-12:
                out.loc[T] = 0.0
                continue

            # 2. Gross normalization (scale down only).
            if gross > self.gross_leverage:
                row = row * (self.gross_leverage / gross)

            # 3. Volatility targeting (causal: trailing returns up to and incl. T).
            pos = returns.index.get_loc(T)
            start = max(0, pos - self.vol_target_window + 1)
            ret_window = returns.iloc[start:pos + 1]
            scale = 1.0
            if len(ret_window) >= max(5, self.vol_target_window // 2):
                ann_vol = self._ex_ante_vol(row, ret_window)
                if ann_vol > 1e-8:
                    scale = self.vol_target_annual / ann_vol
            row = row * scale

            # 4. Hard gross cap after vol scaling.
            gross_after = row.abs().sum()
            if gross_after > self.max_gross:
                row = row * (self.max_gross / gross_after)

            # 5. Re-assert the per-asset concentration cap as a hard final limit.
            #    Vol targeting can lever an asset back above the cap; the cap wins.
            row = row.clip(lower=-self.max_position, upper=self.max_position)

            out.loc[T] = row

        return out.fillna(0.0)


def apply_risk_limits(raw_weights: pd.DataFrame, asset_returns: pd.DataFrame, cfg) -> pd.DataFrame:
    """Convenience wrapper: build a :class:`RiskManager` from config and apply it."""
    return RiskManager.from_config(cfg).apply(raw_weights, asset_returns)
