"""Data-ingestion tests: UTC alignment, missing-bar handling, forward-fill limit."""
import numpy as np
import pandas as pd

from reflexes.data.ingest import _align_and_clean, _as_utc, to_panel, OHLCV_COLUMNS


def test_as_utc_handles_naive_and_aware():
    # Use a fixed UTC offset so the test doesn't depend on system tzdata.
    aware = pd.Timestamp("2021-01-01T00:00:00+05:00")
    assert _as_utc("2021-01-01").tz is not None
    assert str(_as_utc("2021-01-01").tz) == "UTC"
    converted = _as_utc(aware)
    assert str(converted.tz) == "UTC"
    assert converted == pd.Timestamp("2020-12-31T19:00:00", tz="UTC")  # +05:00 -> UTC


def test_align_fills_short_gaps_and_marks_volume_zero():
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=5, freq="D", tz="UTC"))
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": [10, 11, np.nan, np.nan, 14], "volume": 5.0},
        index=idx,
    )
    df.loc[idx[2], ["open", "high", "low", "volume"]] = np.nan
    df.loc[idx[3], ["open", "high", "low", "volume"]] = np.nan
    cleaned, report = _align_and_clean(df, "2021-01-01", "2021-01-05", max_forward_fill=2)
    # Two missing bars, both within the fill limit -> filled, volume set to 0.
    assert report["n_missing"] == 2
    assert report["n_filled"] == 2
    assert cleaned["close"].isna().sum() == 0
    assert cleaned.loc[idx[2], "volume"] == 0.0
    assert cleaned.loc[idx[2], "close"] == 11  # forward-filled from prior close


def test_align_leaves_long_gaps_as_nan():
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=6, freq="D", tz="UTC"))
    close = [10, 11, np.nan, np.nan, np.nan, 15]  # 3-day gap > limit of 2
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": close, "volume": 5.0}, index=idx)
    cleaned, report = _align_and_clean(df, "2021-01-01", "2021-01-06", max_forward_fill=2)
    assert report["n_still_missing"] >= 1  # the far end of the gap stays NaN


def test_align_reindexes_onto_complete_daily_calendar():
    # Missing calendar row entirely (skipped date) must appear as an explicit bar.
    idx = pd.DatetimeIndex(["2021-01-01", "2021-01-03"], tz="UTC")
    df = pd.DataFrame({c: [1.0, 2.0] for c in OHLCV_COLUMNS}, index=idx)
    cleaned, _ = _align_and_clean(df, "2021-01-01", "2021-01-03", max_forward_fill=2)
    assert len(cleaned) == 3  # Jan 1, 2, 3 — the skipped Jan 2 is now present
    assert (cleaned.index == pd.date_range("2021-01-01", "2021-01-03", freq="D", tz="UTC")).all()


def test_to_panel_aligns_assets(frames):
    panel = to_panel(frames, "close")
    assert list(panel.columns) == ["BTC", "ETH", "SOL"]
    assert panel.index.is_monotonic_increasing
