"""Shared fixtures. Synthetic OHLCV so tests never need the network."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reflexes.config import load_config  # noqa: E402


@pytest.fixture
def cfg():
    return load_config()


def _synth_ohlcv(n=400, seed=0, start="2021-06-01", drift=0.0005, vol=0.03):
    rng = np.random.default_rng(seed)
    idx = pd.DatetimeIndex(pd.date_range(start, periods=n, freq="D", tz="UTC"), name="date")
    rets = rng.normal(drift, vol, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
    volume = np.abs(rng.normal(1000, 200, n))
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


@pytest.fixture
def frames():
    return {
        "BTC": _synth_ohlcv(seed=1, drift=0.0006),
        "ETH": _synth_ohlcv(seed=2, drift=0.0004),
        "SOL": _synth_ohlcv(seed=3, drift=0.0008),
    }


@pytest.fixture
def synth_ohlcv():
    return _synth_ohlcv
