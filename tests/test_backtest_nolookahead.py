"""The most important tests: prove the backtest cannot see the future."""
import numpy as np
import pandas as pd
import pytest

from reflexes.backtest.engine import (
    run_backtest, assert_no_lookahead, EXECUTION_LAG_BARS,
)


def _weights(frames, seed=0):
    idx = frames["BTC"].index
    assets = list(frames)
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.uniform(-1, 1, size=(len(idx), len(assets))), index=idx, columns=assets)


def test_held_weights_are_lag2_of_target(cfg, frames):
    tw = _weights(frames)
    res = run_backtest(frames, tw, cfg, verify=True)
    expected = tw.reindex(res.held_weights.index).shift(EXECUTION_LAG_BARS).fillna(0.0)
    pd.testing.assert_frame_equal(res.held_weights, expected, check_dtype=False, atol=1e-12)


def test_no_same_bar_execution(cfg, frames):
    """First EXECUTION_LAG_BARS bars must hold nothing (nothing decided yet)."""
    tw = _weights(frames)
    res = run_backtest(frames, tw, cfg, verify=True)
    assert (res.held_weights.iloc[:EXECUTION_LAG_BARS].abs().sum().sum()) == 0.0


def test_changing_future_targets_leaves_past_pnl_unchanged(cfg, frames):
    """Editing a target at date T must not alter any realized return before T+lag."""
    tw = _weights(frames, seed=1)
    res_a = run_backtest(frames, tw, cfg, verify=True)

    # Perturb the LAST 10 target rows only.
    tw2 = tw.copy()
    cut = tw2.index[-10]
    tw2.loc[cut:] = -tw2.loc[cut:]
    res_b = run_backtest(frames, tw2, cfg, verify=True)

    # Returns strictly before the perturbation reaches the book must be identical.
    boundary = tw.index.get_loc(cut) + EXECUTION_LAG_BARS
    unaffected = res_a.returns.index[:boundary]
    pd.testing.assert_series_equal(
        res_a.returns.loc[unaffected], res_b.returns.loc[unaffected], atol=1e-12
    )


def test_assert_no_lookahead_catches_shift1():
    """A shift(1) alignment (same-bar-ish) must trip the lookahead assertion."""
    idx = pd.DatetimeIndex(pd.date_range("2021-01-01", periods=20, freq="D", tz="UTC"))
    tw = pd.DataFrame(np.random.default_rng(0).uniform(-1, 1, (20, 2)), index=idx, columns=["A", "B"])
    good = tw.shift(EXECUTION_LAG_BARS)
    assert_no_lookahead(tw, good.fillna(0.0))  # passes
    bad = tw.shift(1)  # one bar too eager -> lookahead
    with pytest.raises(AssertionError):
        assert_no_lookahead(tw, bad.fillna(0.0))


def test_costs_reduce_returns(cfg, frames):
    tw = _weights(frames, seed=2)
    res = run_backtest(frames, tw, cfg, verify=True)
    assert (res.returns <= res.gross_returns + 1e-12).all()
    assert res.costs.sum() > 0  # random weights churn, so costs are paid
