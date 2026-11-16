"""Named, versioned parameters. Valuation code may only read assumptions through a ParamSet."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .valuation.types import Range

_LENSES = ("liquidation", "going_concern")
_HAIRCUTS = (
    "cash", "restricted_cash", "securities", "receivables", "inventory_fg", "inventory_wip",
    "inventory_rm", "inventory_unclassified", "land", "buildings", "equipment", "cip",
    "ppe_unclassified", "rou", "goodwill", "book_intangibles", "dta", "other_current",
    "other_noncurrent",
)
REQUIRED: frozenset[str] = frozenset(
    [f"haircut.{lens}.{h}" for lens in _LENSES for h in _HAIRCUTS]
    + [
        "tax.rate",
        "intangible.rd_life_years", "intangible.brand_sga_share", "intangible.brand_life_years",
        "intangible.sga_includes_rd", "intangible.replacement_rd_years",
        "intangible.replacement_sga_years", "intangible.replacement_avg_years",
        "intangible.royalty_rate", "intangible.royalty_discount_rate",
        "intangible.royalty_life_years", "intangible.selection",
        "liability.deferred_revenue_cost_to_fulfil", "liability.pension_rate_shift",
        "liability.pension_duration_years", "liability.contingent_possible_fraction",
        "liability.guarantee_fraction", "liability.purchase_obligation_fraction",
        "decision.margin_of_safety", "decision.buy_requires_liquidation_floor",
        "mapping.residual_tolerance", "market.max_price_stale_days",
    ]
)
SCENARIOS = ("low", "base", "high")


class ParamError(ValueError):
    pass


def _check_entry(name: str, entry: Any) -> dict:
    if not isinstance(entry, dict):
        raise ParamError(f"{name}: expected a mapping, got {entry!r}")
    keys = set(entry) - {"note"}
    if keys != {"value"} and keys != set(SCENARIOS):
        raise ParamError(f"{name}: give either `value` or all of low/base/high (got {sorted(keys)})")
    return entry


class ParamSet:
    def __init__(self, version: str, entries: dict[str, dict], applied: list[str] | None = None):
        self.version = version
        self.entries = entries
        self.applied = applied or []

    # ----------------------------------------------------------------- access
    def triple(self, name: str) -> tuple[Any, Any, Any]:
        try:
            e = self.entries[name]
        except KeyError:
            raise ParamError(f"Unknown parameter {name!r}") from None
        if "value" in e:
            return (e["value"],) * 3
        return e["low"], e["base"], e["high"]

    def rng(self, name: str) -> Range:
        lo, ba, hi = self.triple(name)
        return Range(low=float(lo), base=float(ba), high=float(hi))

    # ------------------------------------------------------------- versioning
    @property
    def hash(self) -> str:
        values = {k: [v for v in self.triple(k)] for k in sorted(self.entries)}
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:16]

    def to_json(self) -> dict:
        return {"version": self.version, "hash": self.hash, "applied_overrides": self.applied,
                "params": self.entries}

    @classmethod
    def from_json(cls, doc: dict) -> "ParamSet":
        return cls(doc["version"], doc["params"], doc.get("applied_overrides"))

    def with_base(self, name: str, value: Any) -> "ParamSet":
        """Copy with one parameter's base value replaced (used by the sensitivity table)."""
        entries = copy.deepcopy(self.entries)
        lo, _, hi = self.triple(name)
        entries[name] = {"low": lo, "base": value, "high": hi}
        return ParamSet(self.version, entries, self.applied)


def load_params(directory: str | Path, sic: int | None = None, ticker: str | None = None) -> ParamSet:
    """Load a parameter folder and resolve industry (by SIC) and company (by ticker) overrides."""
    doc = yaml.safe_load((Path(directory) / "params.yaml").read_text())
    entries = {k: _check_entry(k, v) for k, v in doc["params"].items()}
    missing, unknown = REQUIRED - set(entries), set(entries) - REQUIRED
    if missing or unknown:
        raise ParamError(f"params.yaml: missing {sorted(missing)}, unknown {sorted(unknown)}")

    applied: list[str] = []

    def apply(label: str, overrides: dict) -> None:
        for k, v in overrides.items():
            if k not in REQUIRED:
                raise ParamError(f"{label}: unknown parameter {k!r}")
            entries[k] = _check_entry(k, v)
        applied.append(label)

    if sic is not None:
        for ind in doc.get("industry_overrides") or []:
            lo, hi = ind["sic"]
            if lo <= sic <= hi:
                apply(f"industry:{ind['name']}", ind["params"])
                break
    if ticker and ticker.upper() in (doc.get("company_overrides") or {}):
        apply(f"company:{ticker.upper()}", doc["company_overrides"][ticker.upper()])
    return ParamSet(str(doc["version"]), entries, applied)
