"""LLM-reasoning combiner (swappable with the rules combiner).

This module hands the canonical signal frame for a single decision date to a Claude
model and asks it to return a target weight per asset plus a short rationale. It is a
drop-in alternative to :class:`RulesCombiner` so the two can be compared honestly.

Honesty guarantees:
    * If ``ANTHROPIC_API_KEY`` is not set (and no `ant` profile resolves), the combiner
      returns FLAT weights for every asset and flags ``llm_configured=False`` rather
      than fabricating positions.
    * The model only ever sees signals observable at or before the decision date — the
      backtest passes it one row at a time, so there is no lookahead here.
    * Structured outputs (`output_config.format`) guarantee the response parses; a
      refusal or malformed reply falls back to FLAT + a flag, never a silent guess.

Cost note: a full daily backtest would issue one API call per day per rebalance, which
is slow and costly. In practice, use the LLM combiner for a bounded date range to
compare against the rules combiner, not for a multi-year sweep. The backtest CLI warns
when the LLM combiner is selected over a long horizon.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from .base import Combiner, Decision
from ..features.assemble import CANONICAL_SIGNALS

_POSITION_SCHEMA = {
    "type": "object",
    "properties": {
        "positions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "asset": {"type": "string"},
                    "weight": {"type": "number"},
                    "rationale": {"type": "string"},
                },
                "required": ["asset", "weight", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["positions"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a disciplined quantitative crypto allocator. You receive a set of "
    "normalized daily signals (each in [-1, 1]) for one or more assets, observed at a "
    "single decision date. Return a target weight in [-1, 1] per asset, where positive "
    "is long, negative is short, and 0 is flat. Base the decision only on the signals "
    "provided; do not invent data or reference anything after the decision date. Keep "
    "gross exposure sensible (portfolio-level risk limits are applied downstream). Give "
    "a one-sentence rationale per asset tied to the signals."
)


class LLMCombiner(Combiner):
    name = "llm"

    def __init__(self, cfg):
        self.model = cfg.get("model", "claude-opus-4-8")
        self.max_tokens = int(cfg.get("max_tokens", 2048))
        self._client = None
        self._configured = None  # lazily determined

    # -- client management --------------------------------------------------
    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic  # imported lazily so the package isn't a hard dependency
        except ImportError:
            self._configured = False
            return None
        # Anthropic() resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant` profile.
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            self._configured = False
            return None
        try:
            self._client = anthropic.Anthropic()
            self._configured = True
        except Exception:
            self._configured = False
            self._client = None
        return self._client

    # -- decision -----------------------------------------------------------
    def _flat(self, date, assets, reason) -> Decision:
        return Decision(
            date=date,
            weights={a: 0.0 for a in assets},
            rationale=f"LLM combiner not used: {reason}. All positions FLAT.",
            meta={"llm_configured": False, "reason": reason},
        )

    def decide(self, date: pd.Timestamp, signals: dict[str, pd.Series]) -> Decision:
        assets = list(signals.keys())
        client = self._get_client()
        if client is None:
            return self._flat(date, assets, "no ANTHROPIC_API_KEY / anthropic SDK unavailable")

        # Compact, machine-readable payload of just the canonical signals.
        payload = {
            "decision_date": str(pd.Timestamp(date).date()),
            "signals_per_asset": {
                a: {s: (None if pd.isna(signals[a].get(s)) else round(float(signals[a].get(s)), 4))
                    for s in CANONICAL_SIGNALS}
                for a in assets
            },
            "instructions": "Return one position per asset with weight in [-1, 1].",
        }

        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM,
                output_config={"format": {"type": "json_schema", "schema": _POSITION_SCHEMA}},
                messages=[{"role": "user", "content": json.dumps(payload)}],
            )
        except Exception as exc:  # network / API error -> honest fallback
            return self._flat(date, assets, f"API error: {type(exc).__name__}")

        if getattr(resp, "stop_reason", None) == "refusal":
            return self._flat(date, assets, "model refused")

        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
        if not text:
            return self._flat(date, assets, "empty response")

        try:
            parsed = json.loads(text)
            positions = {p["asset"]: p for p in parsed["positions"]}
        except (json.JSONDecodeError, KeyError, TypeError):
            return self._flat(date, assets, "unparseable response")

        weights, parts = {}, []
        for a in assets:
            p = positions.get(a)
            if p is None:
                weights[a] = 0.0
                continue
            w = float(max(-1.0, min(1.0, p.get("weight", 0.0))))
            weights[a] = w
            parts.append(f"{a}: w={w:+.2f} — {p.get('rationale', '').strip()}")

        return Decision(
            date=date,
            weights=weights,
            rationale=" | ".join(parts),
            meta={"llm_configured": True, "model": self.model},
        )
