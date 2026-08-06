"""Combiner interface shared by the rules-based and LLM-based decision engines.

A combiner turns the canonical signal frame at decision date ``T`` into a set of
*raw target weights* in [-1, 1] per asset (long/flat/short intent, before any
portfolio-level risk sizing) plus a human-readable rationale.

Keeping the two implementations behind one interface is the whole point: you can run
the same backtest with ``combiner: rules`` or ``combiner: llm`` and compare honestly.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Decision:
    """A dated decision: raw target weight per asset plus a rationale string."""
    date: pd.Timestamp
    weights: dict[str, float]
    rationale: str = ""
    meta: dict = field(default_factory=dict)


class Combiner(abc.ABC):
    """Base class. Subclasses implement :meth:`decide` for a single date."""

    name: str = "base"

    @abc.abstractmethod
    def decide(self, date: pd.Timestamp, signals: dict[str, pd.Series]) -> Decision:
        """Return a :class:`Decision` for ``date`` given ``{asset: signal_series}``.

        ``signals[asset]`` is the canonical signal row (index = signal names) as
        observed at ``date``'s close. Implementations MUST NOT look beyond ``date``.
        """

    def run(self, signal_panel: dict[str, pd.DataFrame],
            dates: pd.DatetimeIndex | None = None) -> pd.DataFrame:
        """Apply :meth:`decide` across all dates, returning a date x asset weight frame.

        The default implementation loops date-by-date (needed for the LLM combiner).
        Vectorizable combiners may override this for speed.
        """
        assets = list(signal_panel.keys())
        if dates is None:
            dates = signal_panel[assets[0]].index
        rows = []
        rationales = {}
        for T in dates:
            row_signals = {a: signal_panel[a].loc[T] for a in assets if T in signal_panel[a].index}
            decision = self.decide(T, row_signals)
            rows.append(pd.Series(decision.weights, name=T))
            rationales[T] = decision.rationale
        weights = pd.DataFrame(rows).reindex(columns=assets)
        weights.index.name = "date"
        weights.attrs["rationales"] = rationales
        weights.attrs["combiner"] = self.name
        return weights


def make_combiner(cfg) -> Combiner:
    """Factory: build the combiner named by ``cfg['decision']['combiner']``."""
    from .rules import RulesCombiner
    from .llm import LLMCombiner

    kind = cfg["decision"]["combiner"]
    if kind == "rules":
        return RulesCombiner(cfg["decision"]["rules"])
    if kind == "llm":
        return LLMCombiner(cfg["decision"]["llm"])
    raise ValueError(f"Unknown combiner: {kind!r} (expected 'rules' or 'llm')")
