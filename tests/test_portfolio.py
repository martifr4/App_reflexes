"""Risk-manager tests: concentration cap, gross cap, vol targeting."""
import numpy as np
import pandas as pd

from reflexes.portfolio.risk import RiskManager


def _returns(index, assets, vol=0.03, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0, vol, size=(len(index), len(assets))),
                        index=index, columns=assets)


def test_max_position_cap():
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=60, freq="D", tz="UTC"))
    assets = ["A", "B"]
    raw = pd.DataFrame(1.0, index=idx, columns=assets)  # both want full weight
    rm = RiskManager(max_position=0.5, gross_leverage=5.0, vol_target_annual=10.0,
                     vol_target_window=21, max_gross=10.0)
    out = rm.apply(raw, _returns(idx, assets))
    # No single asset above the cap (0.5) even before vol scaling could push it.
    assert (out.abs() <= 0.5 + 1e-9).all().all()


def test_max_gross_cap():
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=60, freq="D", tz="UTC"))
    assets = ["A", "B", "C"]
    raw = pd.DataFrame(1.0, index=idx, columns=assets)
    # Very low vol -> vol targeting tries to lever up massively; max_gross must clip it.
    rm = RiskManager(max_position=1.0, gross_leverage=3.0, vol_target_annual=100.0,
                     vol_target_window=21, max_gross=1.5)
    out = rm.apply(raw, _returns(idx, assets, vol=0.001))
    gross = out.abs().sum(axis=1)
    assert (gross <= 1.5 + 1e-6).all()


def test_vol_target_scales_down_high_vol():
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=120, freq="D", tz="UTC"))
    assets = ["A"]
    raw = pd.DataFrame(1.0, index=idx, columns=assets)
    high_vol = _returns(idx, assets, vol=0.10, seed=1)   # ~191% annual
    rm = RiskManager(max_position=1.0, gross_leverage=1.0, vol_target_annual=0.40,
                     vol_target_window=21, max_gross=1.5)
    out = rm.apply(raw, high_vol)
    # After warmup, a very high realized vol should be scaled well below full weight.
    assert out["A"].iloc[-1] < 0.5


def test_flat_input_stays_flat():
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=30, freq="D", tz="UTC"))
    assets = ["A", "B"]
    raw = pd.DataFrame(0.0, index=idx, columns=assets)
    rm = RiskManager(max_position=0.5, gross_leverage=1.0, vol_target_annual=0.4,
                     vol_target_window=21, max_gross=1.5)
    out = rm.apply(raw, _returns(idx, assets))
    assert (out == 0.0).all().all()
