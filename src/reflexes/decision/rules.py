"""Transparent, rules-based signal combiner.

The score for each asset is a weighted sum of its canonical signals. The mapping from
score to a raw target weight is a simple, inspectable threshold rule:

    score >  long_threshold   -> long  (weight = clip(score, 0, 1))
    score <  short_threshold  -> short (weight = clip(score, -1, 0))  [if allow_short]
    otherwise                 -> flat  (0)

Everything is deterministic and explainable — the rationale lists each signal's
contribution — which makes this the honest baseline the LLM combiner must beat.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Combiner, Decision


class RulesCombiner(Combiner):
    name = "rules"

    def __init__(self, cfg):
        self.weights = dict(cfg["weights"])
        self.long_threshold = float(cfg["long_threshold"])
        self.short_threshold = float(cfg["short_threshold"])
        self.allow_short = bool(cfg.get("allow_short", True))

    def _score(self, signal_row: pd.Series) -> tuple[float, dict]:
        contributions = {}
        total = 0.0
        for name, w in self.weights.items():
            val = signal_row.get(name, np.nan)
            if pd.isna(val):
                continue
            c = w * float(val)
            contributions[name] = c
            total += c
        return total, contributions

    def _to_weight(self, score: float) -> float:
        if score > self.long_threshold:
            return float(np.clip(score, 0.0, 1.0))
        if score < self.short_threshold and self.allow_short:
            return float(np.clip(score, -1.0, 0.0))
        return 0.0

    def decide(self, date: pd.Timestamp, signals: dict[str, pd.Series]) -> Decision:
        weights: dict[str, float] = {}
        parts: list[str] = []
        for asset, row in signals.items():
            score, contrib = self._score(row)
            w = self._to_weight(score)
            weights[asset] = w
            if contrib:
                top = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:3]
                drivers = ", ".join(f"{k}{'+' if v >= 0 else ''}{v:.2f}" for k, v in top)
                stance = "LONG" if w > 0 else "SHORT" if w < 0 else "FLAT"
                parts.append(f"{asset}: score={score:+.2f} -> {stance} (w={w:+.2f}); {drivers}")
        return Decision(date=date, weights=weights, rationale=" | ".join(parts))

    def run(self, signal_panel, dates=None) -> pd.DataFrame:
        """Vectorized override: compute scores and threshold rule across all dates."""
        assets = list(signal_panel.keys())
        scores = {}
        for asset in assets:
            sf = signal_panel[asset]
            score = sum(self.weights.get(c, 0.0) * sf[c] for c in sf.columns if c in self.weights)
            scores[asset] = score
        score_df = pd.DataFrame(scores)
        if dates is not None:
            score_df = score_df.reindex(dates)

        long_leg = score_df.where(score_df > self.long_threshold).clip(lower=0.0, upper=1.0)
        weights = long_leg
        if self.allow_short:
            short_leg = score_df.where(score_df < self.short_threshold).clip(lower=-1.0, upper=0.0)
            weights = long_leg.fillna(short_leg)
        weights = weights.fillna(0.0)
        weights.index.name = "date"
        weights.attrs["combiner"] = self.name
        weights.attrs["scores"] = score_df
        return weights
