"""Run context: the only way valuation code reaches facts and parameters, so both get recorded."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import yaml

from ..params import ParamSet
from ..store.store import Entity, Fact, FactStore, Tier2Fact
from .types import FactRef, Gap, Range


class MappingError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_mapping() -> dict:
    return yaml.safe_load(resources.files("valuer.mapping").joinpath("line_items.yaml").read_text())


@dataclass(frozen=True)
class Found:
    value: float
    facts: tuple[Fact, ...]
    date: dt.date
    stale: bool

    @property
    def ids(self) -> list[str]:
        return [f.fact_id for f in self.facts]


class Ctx:
    def __init__(self, store: FactStore, entity: Entity, as_of: dt.date, params: ParamSet,
                 knowledge_time: dt.datetime):
        self.store = store
        self.knowledge_time = knowledge_time
        self.entity = entity
        self.cik = entity.cik
        self.as_of = as_of
        self.params = params
        self.mapping = load_mapping()
        self.balance_date, self.annual_date = store.balance_dates(entity.cik, as_of)
        self.facts_used: dict[str, FactRef] = {}
        self.params_used: set[str] = set()
        self.gaps: list[Gap] = []

    # ------------------------------------------------------------- parameters
    def p(self, name: str) -> Range:
        self.params_used.add(name)
        return self.params.rng(name)

    def p_triple(self, name: str) -> tuple:
        self.params_used.add(name)
        return self.params.triple(name)

    # ------------------------------------------------------------------ facts
    def record(self, *facts: Fact | Tier2Fact) -> list[str]:
        for f in facts:
            extra = {}
            if isinstance(f, Tier2Fact):
                extra = dict(tier=2, status=f.status, document=f.document, paragraph=f.paragraph,
                             quote=f.quote, number_text=f.number_text, scale=f.scale, note=f.note)
            self.facts_used[f.fact_id] = FactRef(
                concept=f"{f.taxonomy}:{f.concept}", unit=f.unit, period_start=f.period_start,
                period_end=f.period_end, value=f.value, form=f.form, filed=f.filed, accession=f.accession,
                **extra,
            )
        return [f.fact_id for f in facts]

    def tier2(self, key: str) -> Tier2Fact | None:
        """A figure an agent read from the current filings' text, if one has been recorded."""
        f = self.store.tier2(self.cik, key, self.as_of, self.knowledge_time,
                             sorted({self.balance_date, self.annual_date}))
        if f is not None:
            self.record(f)
        return f

    def _at(self, option: list[str], date: dt.date, unit: str) -> tuple[Fact, ...] | None:
        facts = [self.store.instant(self.cik, c, date, self.as_of, unit) for c in option]
        return None if any(f is None for f in facts) else tuple(facts)  # type: ignore[arg-type]

    def lookup(self, options: list[list[str]], unit: str = "USD", allow_stale: bool = True,
               at: dt.date | None = None) -> Found | None:
        """First option fully reported at the balance date; else, at the last fiscal year end (stale)."""
        dates = [at] if at else [self.balance_date] + (
            [self.annual_date] if allow_stale and self.annual_date != self.balance_date else []
        )
        for date in dates:
            for option in options:
                facts = self._at(option, date, unit)
                if facts is not None:
                    self.record(*facts)
                    return Found(sum(f.value for f in facts), facts, date, date != self.balance_date)
        return None

    def require(self, options: list[list[str]], what: str) -> Found:
        f = self.lookup(options, allow_stale=False)
        if f is None:
            raise MappingError(f"{self.entity.ticker}: {what} not reported at {self.balance_date} ({options})")
        return f

    def annual_flow(self, concepts: list[str]) -> list[Fact]:
        """Fiscal-year series, newest first. For each year the first concept that has a value wins."""
        by_end: dict[dt.date, Fact] = {}
        for c in concepts:
            for f in self.store.annual_series(self.cik, c, self.as_of, self.annual_date):
                by_end.setdefault(f.period_end, f)
        return [by_end[k] for k in sorted(by_end, reverse=True)]

    def gap(self, key: str, description: str) -> None:
        if not any(g.key == key for g in self.gaps):
            self.gaps.append(Gap(key=key, description=description))
