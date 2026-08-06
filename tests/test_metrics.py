"""Metric tests with hand-checkable inputs."""
import numpy as np
import pandas as pd

from reflexes.backtest.metrics import compute_metrics, ANNUAL


def test_zero_returns():
    r = pd.Series(np.zeros(100))
    m = compute_metrics(r)
    assert m["ann_return"] == 0.0
    assert np.isnan(m["sharpe"]) or m["sharpe"] == 0.0


def test_positive_drift_positive_sharpe():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.01, 1000))  # clear positive drift
    m = compute_metrics(r)
    assert m["sharpe"] > 0
    assert m["cagr"] > 0
    assert 0.4 < m["hit_rate"] < 0.6


def test_max_drawdown_of_known_curve():
    # equity goes 1 -> 2 -> 1 -> 1.5 : max drawdown is -50%.
    equity = pd.Series([1.0, 2.0, 1.0, 1.5])
    returns = equity.pct_change().fillna(0.0)
    m = compute_metrics(returns, equity=equity)
    assert np.isclose(m["max_drawdown"], -0.5, atol=1e-9)


def test_annualization_factor_is_365():
    r = pd.Series([0.001] * 730)  # 2 years of constant daily return
    m = compute_metrics(r)
    assert np.isclose(m["ann_return"], 0.001 * ANNUAL, atol=1e-9)
    assert m["n_days"] == 730


def test_win_loss_ratio():
    r = pd.Series([0.02, -0.01, 0.02, -0.01])  # avg win 0.02, avg loss -0.01
    m = compute_metrics(r)
    assert np.isclose(m["win_loss_ratio"], 2.0, atol=1e-9)
    assert np.isclose(m["hit_rate"], 0.5, atol=1e-9)
