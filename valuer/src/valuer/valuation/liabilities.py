"""Liabilities: reported total at face, line by line, plus off-balance-sheet items and claims
that rank ahead of common equity. Ranges follow the valuation scenario, so `low` is the largest."""
from __future__ import annotations

from .context import Ctx, MappingError
from .types import Line, Range

_ABSENT = "is not tagged in the XBRL company facts. Confirm from the footnotes whether one exists."
_SEARCHED = ("An analyst agent searched the current filings and found none disclosed. "
             "Code cannot verify an absence, so check this yourself if it matters.")
_TIER2_NOTE = "Read from the filing text by an agent and checked against that text by code."


def _exposure(ctx: Ctx, options: list, tier2_key: str) -> tuple[float | None, list[str], list[str], str]:
    """(amount, fact ids, notes, state) from XBRL if tagged, else from a tier-2 fact.
    state is found | not_disclosed | unknown."""
    f = ctx.lookup(options)
    if f is not None:
        return f.value, f.ids, [], "found"
    t = ctx.tier2(tier2_key)
    if t is None:
        return None, [], [], "unknown"
    if t.status != "found":
        return None, [t.fact_id], [], "not_disclosed"
    return t.value, [t.fact_id], [_TIER2_NOTE], "found"


def _face(key: str, label: str, amount: float, facts: list[str], notes: list[str] | None = None) -> Line:
    r = Range.const(amount)
    return Line(key=key, label=label, book=amount, liquidation=r, going_concern=r, facts=facts,
                formula="reported amount", notes=notes or [])


def _total(ctx: Ctx, spec: dict) -> tuple[float, list[str]]:
    total = ctx.lookup(spec["total"], allow_stale=False)
    if total is not None:
        return total.value, total.ids
    le = ctx.lookup(spec["liabilities_and_equity"], allow_stale=False)
    eq = ctx.lookup(spec["equity_incl_nci"], allow_stale=False)
    if le is None or eq is None:
        raise MappingError(f"{ctx.entity.ticker}: total liabilities cannot be derived at {ctx.balance_date}")
    temp = ctx.lookup(spec["temporary_equity"], allow_stale=False)
    return le.value - eq.value - (temp.value if temp else 0.0), le.ids + eq.ids + (temp.ids if temp else [])


def value_liabilities(ctx: Ctx, assets: list[Line]) -> list[Line]:
    spec = ctx.mapping["liabilities"]
    total, total_ids = _total(ctx, spec)
    lines: list[Line] = []

    debt = ctx.lookup(spec["debt"], allow_stale=False)
    if debt and debt.value:
        lines.append(_face("debt", "Debt", debt.value, debt.ids, ["Carrying amount, which is face value less small issue costs."]))
    lease = ctx.lookup(spec["operating_lease"], allow_stale=False)
    if lease and lease.value:
        lines.append(_face("operating_lease", "Operating lease liabilities", lease.value, lease.ids))
    dr = ctx.lookup(spec["deferred_revenue"], allow_stale=False)
    if dr and dr.value:
        v = ctx.p("liability.deferred_revenue_cost_to_fulfil") * dr.value
        lines.append(Line(key="deferred_revenue", label="Deferred revenue (at cost to fulfil)", book=dr.value,
                          liquidation=v, going_concern=v, facts=dr.ids,
                          params=["liability.deferred_revenue_cost_to_fulfil"], formula="book x cost-to-fulfil fraction"))

    other = total - sum(x.book for x in lines)
    if other < -ctx.p("mapping.residual_tolerance").base * total:
        raise MappingError(f"{ctx.entity.ticker}: mapped liabilities exceed the reported total by {-other:,.0f}")
    lines.append(_face("other_liabilities", "All other liabilities", other, total_ids,
                       ["Residual: payables, accruals, pensions, deferred taxes and everything else, at the reported amount."]))

    # ---- adjustments and off-balance-sheet items (book = 0: none is inside reported liabilities)
    def scaled(key: str, label: str, options_key: str, tier2_key: str, param: str, gap: str) -> None:
        amount, ids, notes, state = _exposure(ctx, spec[options_key], tier2_key)
        if state != "found":
            ctx.gap(key, f"{gap}: {_SEARCHED}" if state == "not_disclosed" else f"{gap} {_ABSENT}")
            return
        if not amount:
            return
        v = ctx.p(param) * amount
        lines.append(Line(key=key, label=label, book=0.0, liquidation=v, going_concern=v, facts=ids,
                          params=[param], formula="reported exposure x fraction", notes=notes))

    pbo, ids, notes, state = _exposure(ctx, spec["pension_obligation"], "pension_benefit_obligation")
    if state != "found":
        ctx.gap("pension_repricing", f"The pension benefit obligation: {_SEARCHED}" if state == "not_disclosed"
                else f"The pension benefit obligation {_ABSENT} The low-scenario re-pricing is not applied.")
    elif pbo:
        shift, dur = ctx.p("liability.pension_rate_shift"), ctx.p("liability.pension_duration_years")
        v = shift * dur * pbo
        lines.append(Line(key="pension_repricing", label="Pension re-pricing at a lower discount rate", book=0.0,
                          liquidation=v, going_concern=v, facts=ids,
                          params=["liability.pension_rate_shift", "liability.pension_duration_years"],
                          formula="benefit obligation x duration x rate cut", notes=notes))
    scaled("contingent_possible", "Reasonably possible losses", "contingent_possible", "contingent_possible_loss",
           "liability.contingent_possible_fraction", "An estimate of reasonably possible losses")
    scaled("guarantees", "Guarantees", "guarantees", "guarantee_max_exposure",
           "liability.guarantee_fraction", "A maximum guarantee exposure")
    scaled("purchase_obligations", "Unconditional purchase obligations", "purchase_obligations", "purchase_obligations",
           "liability.purchase_obligation_fraction", "An unconditional purchase obligation total")

    for key, label in (("preferred", "Preferred stock"), ("nci", "Non-controlling interests"),
                       ("redeemable_nci", "Redeemable non-controlling interests")):
        f = ctx.lookup(spec[key], allow_stale=False)
        if f and f.value:
            r = Range.const(f.value)
            lines.append(Line(key=key, label=label, book=0.0, liquidation=r, going_concern=r, facts=f.ids,
                              formula="reported amount", notes=["Ranks ahead of common equity; not part of reported liabilities."]))

    # ---- tax on liquidation gains (liquidation lens only; losses on other lines give no offset)
    rate = ctx.p("tax.rate")
    gains = Range(**{s: sum(max(0.0, getattr(a.liquidation, s) - a.book) for a in assets) for s in ("low", "base", "high")})
    tax = rate * gains
    if any(v > 0 for _, v in tax.items()):
        lines.append(Line(key="liquidation_gain_tax", label="Tax on liquidation gains", book=0.0,
                          liquidation=tax, going_concern=Range.const(0.0), params=["tax.rate"],
                          formula="tax rate x sum of (realisable value - book) where positive",
                          notes=["Liquidation lens only."]))
    return lines
