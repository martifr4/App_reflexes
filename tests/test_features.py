"""Feature tests: the critical property is causality (no lookahead)."""
import numpy as np
import pandas as pd

from reflexes.features.price import price_features
from reflexes.features.volume import volume_features
from reflexes.features.assemble import build_signal_frame, CANONICAL_SIGNALS
from reflexes.features.news import news_features, Headline, score_text


def test_price_features_are_causal(cfg, synth_ohlcv):
    """A feature at time T must not change when future bars are appended."""
    full = synth_ohlcv(n=400, seed=7)
    prefix = full.iloc[:300]
    f_full = price_features(full, cfg["features"])
    f_prefix = price_features(prefix, cfg["features"])
    common = f_prefix.index
    # Values on the shared dates must match to floating tolerance.
    pd.testing.assert_frame_equal(
        f_full.loc[common], f_prefix.loc[common], check_exact=False, atol=1e-9
    )


def test_signals_bounded(cfg, synth_ohlcv):
    df = synth_ohlcv(n=500, seed=3)
    sig = build_signal_frame(df, cfg["features"])
    assert list(sig.columns) == CANONICAL_SIGNALS
    valid = sig.dropna()
    assert (valid.abs() <= 1.0 + 1e-9).all().all()


def test_drawdown_is_nonpositive(cfg, synth_ohlcv):
    df = synth_ohlcv(n=300, seed=4)
    f = price_features(df, cfg["features"])
    assert (f["drawdown"].dropna() <= 1e-12).all()


def test_volume_features_run(cfg, synth_ohlcv):
    df = synth_ohlcv(n=300, seed=5)
    v = volume_features(df, cfg["features"])
    assert "vol_trend" in v.columns and "vol_price_div" in v.columns
    assert set(v["vol_price_div"].dropna().unique()).issubset({-1.0, 0.0, 1.0})


def test_news_neutral_when_disabled():
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=5, freq="D", tz="UTC"))
    out = news_features(idx, {"enabled": False})
    assert (out["news_sentiment"] == 0.0).all()
    assert (~out["news_available"]).all()


def test_news_no_lookahead():
    """Only headlines strictly before decision date T may be used."""
    idx = pd.DatetimeIndex(pd.date_range("2021-01-02", periods=3, freq="D", tz="UTC"))
    headlines = [
        Headline(pd.Timestamp("2021-01-01T12:00", tz="UTC"), "bullish surge adoption"),   # before Jan 2
        Headline(pd.Timestamp("2021-01-02T12:00", tz="UTC"), "crash hack selloff"),        # ON Jan 2 -> excluded for Jan 2
    ]
    out = news_features(idx, {"enabled": True, "lookback_days": 5}, headlines=headlines)
    # Jan 2 decision (00:00 UTC) may only see the Jan 1 positive headline.
    assert out.loc[idx[0], "news_available"]
    assert out.loc[idx[0], "news_sentiment"] > 0
    # Jan 3 decision can now see the Jan 2 negative headline too -> net drops.
    assert out.loc[idx[1], "news_sentiment"] < out.loc[idx[0], "news_sentiment"]


def test_score_text():
    assert score_text("surge rally bullish") > 0
    assert score_text("crash hack ban") < 0
    assert score_text("the quick brown fox") == 0.0
