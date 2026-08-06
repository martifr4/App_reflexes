"""Assemble raw price/volume/news features into a canonical, normalized signal panel.

The combiners (rules and LLM) should not depend on the exact feature engineering.
So we collapse the many raw features into a small set of *canonical signals*, each in
[-1, 1], with a stable, documented meaning:

    momentum : long-horizon trend-following (12-1 momentum), rolling z then tanh
    trend    : price vs. medium/long moving averages
    meanrev  : short-horizon reversal (fade the last week)
    volume   : participation trend, gated by volume-price confirmation
    news     : sentiment in [-1, 1] (0 and flagged when unavailable)

All normalization is causal (rolling windows use only past+present). NaN during the
warm-up period is preserved so the backtest can require signal availability before it
takes any position.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .price import price_features
from .volume import volume_features
from .news import news_features

CANONICAL_SIGNALS = ["momentum", "trend", "meanrev", "volume", "news"]


def _rolling_z(s: pd.Series, window: int) -> pd.Series:
    mu = s.rolling(window, min_periods=window // 2).mean()
    sd = s.rolling(window, min_periods=window // 2).std()
    return (s - mu) / sd.replace(0.0, np.nan)


def _squash(s: pd.Series) -> pd.Series:
    """Map an unbounded score to [-1, 1] smoothly."""
    return np.tanh(s)


def build_signal_frame(ohlcv: pd.DataFrame, cfg, news_frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the canonical signal frame for one asset.

    Parameters
    ----------
    ohlcv: single-asset OHLCV frame.
    cfg: the ``features`` sub-config.
    news_frame: optional per-date news frame (from :func:`news_features`).
    """
    px = price_features(ohlcv, cfg)
    vol = volume_features(ohlcv, cfg)
    z_win = cfg["zscore_window"]

    sig = pd.DataFrame(index=ohlcv.index)

    # Momentum: 12-1, z-scored across its own history, squashed.
    sig["momentum"] = _squash(_rolling_z(px["mom_12_1"], z_win))

    # Trend: average of medium/long MA ratios, z-scored.
    ma_cols = [c for c in px.columns if c.startswith("ma_ratio_")]
    long_ma = [c for c in ma_cols if int(c.split("_")[-1]) >= 50]
    trend_raw = px[long_ma].mean(axis=1) if long_ma else px[ma_cols].mean(axis=1)
    sig["trend"] = _squash(_rolling_z(trend_raw, z_win))

    # Mean reversion: fade the last week's return (note the sign flip).
    sig["meanrev"] = _squash(-_rolling_z(px["ret_5"], z_win))

    # Volume: participation trend gated by price confirmation.
    vol_trend_z = _rolling_z(vol["vol_trend"], z_win)
    confirm = vol["vol_price_div"].fillna(0.0)  # +1 confirm, -1 diverge, 0 flat
    sig["volume"] = _squash(vol_trend_z) * confirm.clip(-1, 1)

    # News: already in [-1, 1]; neutral when unavailable.
    if news_frame is not None and "news_sentiment" in news_frame:
        sig["news"] = news_frame.reindex(ohlcv.index)["news_sentiment"].fillna(0.0)
    else:
        sig["news"] = 0.0

    return sig[CANONICAL_SIGNALS]


def build_feature_panel(frames: dict[str, pd.DataFrame], cfg,
                        news_by_asset: dict[str, pd.DataFrame] | None = None) -> dict[str, pd.DataFrame]:
    """Build canonical signal frames for every asset.

    Returns ``{asset: signal_frame}`` where each frame has columns
    :data:`CANONICAL_SIGNALS` on the asset's UTC daily index.
    """
    feat_cfg = cfg["features"] if "features" in cfg else cfg
    news_cfg = cfg["news"] if "news" in cfg else {"enabled": False}
    out: dict[str, pd.DataFrame] = {}
    for asset, ohlcv in frames.items():
        nf = None
        if news_cfg.get("enabled", False):
            headlines = (news_by_asset or {}).get(asset)
            nf = news_features(ohlcv.index, news_cfg, headlines=headlines)
        out[asset] = build_signal_frame(ohlcv, feat_cfg, news_frame=nf)
    return out
