"""Price-dynamics features.

Every feature at row ``T`` uses only OHLC data observable at or before ``T``'s close.
There is no forward-looking window here. The backtest layer additionally asserts this
property at the panel level, but keeping it true at the source is the first defense.

Features produced (per asset):
    ret_{h}        : log return over the last h trading days
    mom_12_1       : 12-month momentum skipping the most recent month (classic 12-1)
    ma_ratio_{w}   : close / SMA(w) - 1  (trend relationship)
    ma_slope_{w}   : w-day change in SMA(w), normalized by price (trend direction)
    rv_{w}         : realized volatility (annualized std of daily log returns, window w)
    atr_{w}        : Average True Range over w days, normalized by close
    drawdown       : current drawdown from the running peak of close (<= 0)
    dd_state       : 1 if within 5% of peak, else scaled negative severity in (-1, 1]

Normalized companions (suffix ``_z``) are rolling z-scores; see ``normalize``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _log_return(close: pd.Series, horizon: int) -> pd.Series:
    return np.log(close / close.shift(horizon))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


def price_features(ohlcv: pd.DataFrame, cfg) -> pd.DataFrame:
    """Compute the price feature frame for a single asset.

    Parameters
    ----------
    ohlcv: UTC-indexed frame with columns open, high, low, close, volume.
    cfg: the ``features`` sub-config.
    """
    close = ohlcv["close"]
    high, low = ohlcv["high"], ohlcv["low"]
    out = pd.DataFrame(index=ohlcv.index)

    # Multi-horizon returns.
    for h in cfg["return_horizons"]:
        out[f"ret_{h}"] = _log_return(close, h)

    # Classic 12-1 momentum: cumulative return from t-lookback to t-skip.
    lb, skip = cfg["momentum_lookback"], cfg["momentum_skip"]
    out["mom_12_1"] = np.log(close.shift(skip) / close.shift(lb))

    # Moving-average relationships and slopes.
    for w in cfg["ma_windows"]:
        sma = close.rolling(w, min_periods=w).mean()
        out[f"ma_ratio_{w}"] = close / sma - 1.0
        out[f"ma_slope_{w}"] = (sma - sma.shift(w)) / close

    # Realized volatility (annualized). Daily crypto -> 365-day year.
    daily_ret = np.log(close / close.shift(1))
    w = cfg["vol_window"]
    out[f"rv_{w}"] = daily_ret.rolling(w, min_periods=w).std() * np.sqrt(365.0)

    # ATR, normalized by price so it is comparable across assets.
    aw = cfg["atr_window"]
    out[f"atr_{aw}"] = _atr(high, low, close, aw) / close

    # Drawdown state from the running peak (causal: cummax uses only past+present).
    running_peak = close.cummax()
    drawdown = close / running_peak - 1.0
    out["drawdown"] = drawdown
    # dd_state: 0 near highs, more negative as drawdown deepens, floored at -1.
    out["dd_state"] = drawdown.clip(lower=-1.0)

    return out
