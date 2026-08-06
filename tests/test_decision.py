"""Decision-layer tests: rules combiner logic + LLM combiner honest fallback."""
import os

import numpy as np
import pandas as pd

from reflexes.decision.rules import RulesCombiner
from reflexes.decision.llm import LLMCombiner
from reflexes.features.assemble import CANONICAL_SIGNALS


def _rules_cfg():
    return {
        "weights": {"momentum": 1.0, "trend": 1.0, "meanrev": -0.5, "volume": 0.5, "news": 0.0},
        "long_threshold": 0.15,
        "short_threshold": -0.15,
        "allow_short": True,
    }


def _signal_row(**kw):
    row = {s: 0.0 for s in CANONICAL_SIGNALS}
    row.update(kw)
    return pd.Series(row)


def test_rules_long_short_flat():
    rc = RulesCombiner(_rules_cfg())
    d_long = rc.decide(pd.Timestamp("2021-01-01"), {"A": _signal_row(momentum=0.9, trend=0.9)})
    d_short = rc.decide(pd.Timestamp("2021-01-01"), {"A": _signal_row(momentum=-0.9, trend=-0.9)})
    d_flat = rc.decide(pd.Timestamp("2021-01-01"), {"A": _signal_row(momentum=0.05)})
    assert d_long.weights["A"] > 0
    assert d_short.weights["A"] < 0
    assert d_flat.weights["A"] == 0.0


def test_rules_respects_no_short():
    cfg = _rules_cfg()
    cfg["allow_short"] = False
    rc = RulesCombiner(cfg)
    d = rc.decide(pd.Timestamp("2021-01-01"), {"A": _signal_row(momentum=-0.9, trend=-0.9)})
    assert d.weights["A"] == 0.0  # short suppressed -> flat


def test_rules_vectorized_matches_pointwise(cfg, frames):
    from reflexes.features.assemble import build_feature_panel
    panel = build_feature_panel(frames, cfg)
    rc = RulesCombiner(cfg["decision"]["rules"])
    dates = panel["BTC"].dropna().index[-20:]
    vec = rc.run(panel, dates=dates)
    # Compare a few dates against the pointwise decide().
    for T in dates[:5]:
        row = {a: panel[a].loc[T] for a in panel}
        pt = rc.decide(T, row)
        for a in panel:
            assert np.isclose(vec.loc[T, a], pt.weights[a], atol=1e-9)


def test_llm_combiner_flat_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    lc = LLMCombiner({"model": "claude-opus-4-8", "max_tokens": 512})
    d = lc.decide(pd.Timestamp("2021-01-01"), {"A": _signal_row(momentum=0.9), "B": _signal_row()})
    assert d.weights == {"A": 0.0, "B": 0.0}
    assert d.meta["llm_configured"] is False
    assert "FLAT" in d.rationale
