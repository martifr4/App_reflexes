"""Null-test plumbing: structure, determinism, and percentile ranking."""
import numpy as np
import pandas as pd

from reflexes.backtest.null_test import run_null_test, null_percentile
from reflexes.data.ingest import to_panel


def _raw_weights(frames, seed=0):
    idx = frames["BTC"].index
    assets = list(frames)
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.uniform(-1, 1, size=(len(idx), len(assets))), index=idx, columns=assets)


def test_null_test_structure(cfg, frames):
    cfg["null_test"]["n_shuffles"] = 5
    cfg["backtest"]["oos_start"] = str(frames["BTC"].index[300].date())
    raw = _raw_weights(frames)
    ar = to_panel(frames, "close").pct_change().fillna(0.0)
    res = run_null_test(frames, raw, ar, cfg, mode="random")
    assert res["mode"] == "random"
    assert res["n"] <= 5
    assert "oos_sharpe_mean" in res and "samples" in res


def test_null_deterministic(cfg, frames):
    cfg["null_test"]["n_shuffles"] = 4
    cfg["backtest"]["oos_start"] = str(frames["BTC"].index[300].date())
    raw = _raw_weights(frames)
    ar = to_panel(frames, "close").pct_change().fillna(0.0)
    a = run_null_test(frames, raw, ar, cfg, mode="random")
    b = run_null_test(frames, raw, ar, cfg, mode="random")
    assert a["samples"] == b["samples"]  # seeded -> reproducible


def test_null_percentile():
    res = {"samples": [-2.0, -1.0, 0.0, 1.0]}
    assert null_percentile(res, 0.5) == 0.75  # beats 3 of 4
    assert null_percentile(res, -3.0) == 0.0
