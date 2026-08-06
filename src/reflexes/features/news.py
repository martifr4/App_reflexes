"""News / momentum sentiment — OPTIONAL and deliberately QUARANTINED.

Design stance (per the project brief):
    * This module is OFF by default (``news.enabled: false``).
    * If enabled, it may ONLY use headlines whose publication timestamp is strictly
      earlier than the decision date ``T`` (a 00:00 UTC daily boundary). Any headline
      without a reliable timestamp is discarded — we never guess.
    * If no reliable, timestamped news is available for a date, the feature for that
      date is NEUTRAL (0.0) and the ``news_available`` flag is False. We flag the
      absence rather than fabricate a signal.

The sentiment scorer here is a transparent lexicon (no network, no model dependency)
so the module is fully reproducible. A real deployment could swap in a better scorer,
but the lookahead discipline and the "neutral-when-absent" contract must be preserved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

# Minimal, transparent sentiment lexicon. Intentionally small and auditable.
_POSITIVE = {
    "surge", "rally", "gains", "bullish", "record", "adoption", "approval", "upgrade",
    "partnership", "inflow", "breakout", "soars", "jumps", "milestone", "etf",
}
_NEGATIVE = {
    "crash", "plunge", "hack", "exploit", "bearish", "selloff", "ban", "lawsuit",
    "outflow", "liquidation", "fraud", "collapse", "downgrade", "delay", "sinks",
}


@dataclass
class Headline:
    """A timestamped headline. ``published_utc`` MUST be tz-aware UTC."""
    published_utc: pd.Timestamp
    text: str


def score_text(text: str) -> float:
    """Return a sentiment score in [-1, 1] from the transparent lexicon."""
    tokens = [t.strip(".,!?:;\"'()").lower() for t in text.split()]
    pos = sum(t in _POSITIVE for t in tokens)
    neg = sum(t in _NEGATIVE for t in tokens)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def news_features(index: pd.DatetimeIndex, cfg,
                  headlines: Iterable[Headline] | None = None) -> pd.DataFrame:
    """Produce a per-date news feature frame aligned to ``index`` (UTC daily).

    Columns:
        news_sentiment : mean sentiment of headlines strictly before date T (0 if none)
        news_available : bool flag — True only if >=1 valid, timestamped headline was used

    When ``cfg['enabled']`` is False, or no valid headlines are supplied, every row is
    neutral and flagged unavailable. This is the honest default.
    """
    index = pd.DatetimeIndex(index)
    out = pd.DataFrame(index=index)
    out["news_sentiment"] = 0.0
    out["news_available"] = False

    if not cfg.get("enabled", False) or not headlines:
        return out

    lookback = pd.Timedelta(days=int(cfg.get("lookback_days", 3)))
    # Keep only headlines that carry a real tz-aware UTC timestamp.
    valid = [
        h for h in headlines
        if isinstance(h.published_utc, pd.Timestamp) and h.published_utc.tzinfo is not None
    ]
    if not valid:
        return out

    times = pd.DatetimeIndex([h.published_utc.tz_convert("UTC") for h in valid])
    scores = np.array([score_text(h.text) for h in valid])

    for T in index:
        # STRICT no-lookahead: only headlines with published_utc < T (the 00:00 boundary).
        window_mask = (times < T) & (times >= T - lookback)
        if window_mask.any():
            out.at[T, "news_sentiment"] = float(scores[window_mask].mean())
            out.at[T, "news_available"] = True

    return out
