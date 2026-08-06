"""Volume-dynamics features.

As with price features, every value at ``T`` uses only data at or before ``T``.

Features produced (per asset):
    vol_trend      : log(volume EMA_short / volume median baseline) — participation trend
    vol_zscore     : rolling z-score of log-volume (spikes vs. its own history)
    vol_price_div  : sign-agreement between volume trend and price move over the same
                     window (>0 => volume confirms price direction; <0 => divergence)
    dollar_vol     : close * volume (a crude liquidity proxy), log-scaled and z-scored
    up_vol_share   : share of recent volume occurring on up-days (participation skew)

All features are documented and reproducible from OHLCV alone — no external data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def volume_features(ohlcv: pd.DataFrame, cfg) -> pd.DataFrame:
    close = ohlcv["close"]
    volume = ohlcv["volume"].astype(float)
    out = pd.DataFrame(index=ohlcv.index)

    baseline_w = cfg["volume_baseline_window"]
    short_w = max(5, baseline_w // 6)

    log_vol = np.log1p(volume)
    baseline = volume.rolling(baseline_w, min_periods=baseline_w).median()
    ema_short = volume.ewm(span=short_w, adjust=False, min_periods=short_w).mean()

    # Participation trend: recent volume vs. its slower baseline (guard against 0 baseline).
    safe_baseline = baseline.replace(0.0, np.nan)
    out["vol_trend"] = np.log(ema_short / safe_baseline)

    # Volume spike z-score relative to its own recent distribution.
    mu = log_vol.rolling(baseline_w, min_periods=baseline_w).mean()
    sd = log_vol.rolling(baseline_w, min_periods=baseline_w).std()
    out["vol_zscore"] = (log_vol - mu) / sd.replace(0.0, np.nan)

    # Volume-price divergence: do volume and price move together over short_w?
    price_move = np.sign(close - close.shift(short_w))
    vol_move = np.sign(ema_short - ema_short.shift(short_w))
    out["vol_price_div"] = price_move * vol_move  # +1 confirm, -1 diverge, 0 flat

    # Dollar volume (liquidity proxy), z-scored on log scale.
    dollar = np.log1p(close * volume)
    dmu = dollar.rolling(baseline_w, min_periods=baseline_w).mean()
    dsd = dollar.rolling(baseline_w, min_periods=baseline_w).std()
    out["dollar_vol_z"] = (dollar - dmu) / dsd.replace(0.0, np.nan)

    # Share of recent volume on up-days (participation skew).
    up_day = (close > close.shift(1)).astype(float)
    up_vol = (volume * up_day).rolling(short_w, min_periods=short_w).sum()
    tot_vol = volume.rolling(short_w, min_periods=short_w).sum().replace(0.0, np.nan)
    out["up_vol_share"] = up_vol / tot_vol - 0.5  # centered at 0

    return out
