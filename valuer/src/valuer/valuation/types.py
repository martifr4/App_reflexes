"""Value types. Every number the engine produces is a Range with the facts and parameters behind it."""
from __future__ import annotations

import datetime as dt
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict


class Range(BaseModel):
    """Values in the low / base / high VALUATION scenarios.

    Arithmetic is scenario by scenario. A liability Range therefore holds its largest amount in
    ``low``, because that is the amount used when the equity value is at its lowest.
    """

    model_config = ConfigDict(frozen=True)
    low: float
    base: float
    high: float

    @classmethod
    def const(cls, v: float) -> "Range":
        return cls(low=v, base=v, high=v)

    def _zip(self, other: "Range | float", f: Callable[[float, float], float]) -> "Range":
        o = other if isinstance(other, Range) else Range.const(float(other))
        return Range(low=f(self.low, o.low), base=f(self.base, o.base), high=f(self.high, o.high))

    def __add__(self, o): return self._zip(o, lambda a, b: a + b)
    def __sub__(self, o): return self._zip(o, lambda a, b: a - b)
    def __mul__(self, o): return self._zip(o, lambda a, b: a * b)
    __radd__ = __add__
    __rmul__ = __mul__

    def map(self, f: Callable[[float], float]) -> "Range":
        return Range(low=f(self.low), base=f(self.base), high=f(self.high))

    def items(self):
        return (("low", self.low), ("base", self.base), ("high", self.high))


ZERO = Range.const(0.0)


class Line(BaseModel):
    key: str
    label: str
    book: float  # carrying amount on the balance sheet; 0 for off-balance-sheet items
    liquidation: Range
    going_concern: Range
    facts: list[str] = []
    params: list[str] = []
    formula: str = ""
    notes: list[str] = []


class Totals(BaseModel):
    book: float
    liquidation: Range
    going_concern: Range


class Component(BaseModel):
    label: str
    value: Range


class IntangibleMethod(BaseModel):
    key: str
    label: str
    status: Literal["ok", "insufficient_history"]
    value: Range | None = None
    components: list[Component] = []
    facts: list[str] = []
    params: list[str] = []
    formula: str = ""
    notes: list[str] = []


class Intangibles(BaseModel):
    methods: list[IntangibleMethod]
    selected: Range
    selection: dict[str, str]  # scenario -> rule
    selected_method: dict[str, str]  # scenario -> method key ("none" if no method ran)


class Equity(BaseModel):
    liquidation: Range
    reproduction: Range
    liquidation_per_share: Range
    reproduction_per_share: Range


class Market(BaseModel):
    price: float
    price_date: dt.date
    price_source: str
    price_id: str
    shares_basic: float
    shares_basic_date: dt.date
    dilution_shares: float
    dilution_method: str
    shares_diluted: float
    market_cap: float


class Decision(BaseModel):
    verdict: Literal["BUY", "WATCH", "PASS"]
    margin_of_safety_required: float
    buy_below: float
    watch_below: float
    liquidation_floor: float
    liquidation_floor_required: bool
    implied_margin_of_safety: float | None
    reasons: list[str]


class Sensitivity(BaseModel):
    param: str
    reproduction_base_at_low: float
    reproduction_base_at_high: float
    liquidation_base_at_low: float
    liquidation_base_at_high: float
    swing: float


class Gap(BaseModel):
    key: str
    description: str


class FactRef(BaseModel):
    concept: str
    unit: str
    period_start: dt.date | None
    period_end: dt.date
    value: float
    form: str
    filed: dt.date
    accession: str


class Meta(BaseModel):
    ticker: str
    cik: int
    name: str
    sic: int
    as_of: dt.date
    balance_date: dt.date
    annual_date: dt.date
    price_source: str
    params_version: str
    params_hash: str
    engine_version: str


class Valuation(BaseModel):
    meta: Meta
    assets: list[Line]
    assets_total: Totals
    liabilities: list[Line]
    liabilities_total: Totals
    intangibles: Intangibles
    equity: Equity
    market: Market
    decision: Decision
    sensitivity: list[Sensitivity] = []
    gaps: list[Gap]
    facts_used: dict[str, FactRef]
    params_used: list[str]
