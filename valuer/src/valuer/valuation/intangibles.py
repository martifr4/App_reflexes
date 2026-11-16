"""Non-marketable assets: three independent estimates, reported side by side.

A. Capitalised investment  - past R&D and brand-building spend, straight-line amortised.
B. Replacement cost        - years of current spend an entrant would need to rebuild.
C. Relief from royalty     - after-tax royalties saved on flat revenue over a finite life.

The methods are never averaged. A named rule picks which method's figure enters each scenario.
"""
from __future__ import annotations

from ..store.store import Fact
from .context import Ctx
from .types import Component, IntangibleMethod, Intangibles, Range, ZERO

SCENARIOS = ("low", "base", "high")


def _amortised_stock(spend: list[float], life: int) -> float:
    """Unamortised balance of past spend, newest first, straight-line over ``life`` years."""
    return sum(spend[k] * (life - k) / life for k in range(life))


def _scenario_range(f) -> Range:
    return Range(**{s: f(i) for i, s in enumerate(SCENARIOS)})


def _brand_spend(ctx: Ctx, sga: list[Fact], rd: list[Fact]) -> tuple[list[float], list[str]]:
    """SG&A per year, with R&D removed where the company reports R&D inside SG&A."""
    includes = ctx.p_triple("intangible.sga_includes_rd")[1]
    if not includes:
        return [f.value for f in sga], []
    rd_by_end = {f.period_end: f.value for f in rd}
    return [f.value - rd_by_end.get(f.period_end, 0.0) for f in sga], ["SG&A is taken net of R&D, which this company reports inside SG&A."]


def _capitalised(ctx: Ctx, rd: list[Fact], sga: list[Fact]) -> IntangibleMethod:
    params = ["intangible.rd_life_years", "intangible.brand_sga_share", "intangible.brand_life_years", "intangible.sga_includes_rd"]
    rd_life = [int(x) for x in ctx.p_triple("intangible.rd_life_years")]
    brand_life = [int(x) for x in ctx.p_triple("intangible.brand_life_years")]
    share = ctx.p_triple("intangible.brand_sga_share")
    brand_spend, notes = _brand_spend(ctx, sga, rd)
    base = dict(key="capitalised_investment", label="A. Capitalised investment", params=params,
                formula="sum over years of spend x remaining life / life", notes=notes)
    if (rd and len(rd) < max(rd_life)) or len(sga) < max(brand_life):
        return IntangibleMethod(status="insufficient_history", **base | {
            "notes": notes + [f"Needs {max(rd_life)} fiscal years of R&D and {max(brand_life)} of SG&A in the fact store."]})
    rd_vals = [f.value for f in rd]
    tech = _scenario_range(lambda i: _amortised_stock(rd_vals, rd_life[i])) if rd else ZERO
    brand = _scenario_range(lambda i: _amortised_stock([x * float(share[i]) for x in brand_spend], brand_life[i]))
    used = rd[: max(rd_life)] + sga[: max(brand_life)]
    return IntangibleMethod(
        status="ok", value=tech + brand, facts=ctx.record(*used),
        components=[Component(label="Technology (capitalised R&D)", value=tech),
                    Component(label="Brand and customers (capitalised share of SG&A)", value=brand)],
        **base,
    )


def _replacement(ctx: Ctx, rd: list[Fact], sga: list[Fact]) -> IntangibleMethod:
    params = ["intangible.replacement_rd_years", "intangible.replacement_sga_years",
              "intangible.replacement_avg_years", "intangible.sga_includes_rd"]
    n = int(ctx.p_triple("intangible.replacement_avg_years")[1])
    brand_spend, notes = _brand_spend(ctx, sga, rd)
    base = dict(key="replacement_cost", label="B. Replacement cost", params=params,
                formula="average annual spend x years needed to rebuild", notes=notes)
    if (rd and len(rd) < n) or len(sga) < n:
        return IntangibleMethod(status="insufficient_history", **base | {
            "notes": notes + [f"Needs {n} fiscal years of spend in the fact store."]})
    rd_avg = sum(f.value for f in rd[:n]) / n if rd else 0.0
    sga_avg = sum(brand_spend[:n]) / n
    tech = ctx.p("intangible.replacement_rd_years") * rd_avg
    brand = ctx.p("intangible.replacement_sga_years") * sga_avg
    return IntangibleMethod(
        status="ok", value=tech + brand, facts=ctx.record(*(rd[:n] + sga[:n])),
        components=[Component(label="Technology (years of R&D)", value=tech),
                    Component(label="Brand and customers (years of SG&A)", value=brand)],
        **base,
    )


def _relief_from_royalty(ctx: Ctx, revenue: list[Fact]) -> IntangibleMethod:
    params = ["intangible.royalty_rate", "intangible.royalty_discount_rate", "intangible.royalty_life_years", "tax.rate"]
    base = dict(key="relief_from_royalty", label="C. Relief from royalty", params=params,
                formula="revenue x royalty rate x (1 - tax) x annuity factor(discount rate, life)")
    if not revenue:
        return IntangibleMethod(status="insufficient_history", notes=["No annual revenue in the fact store."], **base)
    rev = revenue[0]
    rate, disc, tax = ctx.p("intangible.royalty_rate"), ctx.p("intangible.royalty_discount_rate"), ctx.p("tax.rate")
    life = [int(x) for x in ctx.p_triple("intangible.royalty_life_years")]

    def pv(i: int) -> float:
        s = SCENARIOS[i]
        r = getattr(disc, s)
        annuity = sum(1 / (1 + r) ** t for t in range(1, life[i] + 1))
        return rev.value * getattr(rate, s) * (1 - getattr(tax, s)) * annuity

    return IntangibleMethod(status="ok", value=_scenario_range(pv), facts=ctx.record(rev),
                            notes=["Revenue is held flat at the last fiscal year; no growth is assumed."], **base)


_RULES = {"min": lambda xs: xs[0], "lower_median": lambda xs: xs[(len(xs) - 1) // 2], "max": lambda xs: xs[-1]}


def value_intangibles(ctx: Ctx) -> Intangibles:
    flows = ctx.mapping["flows"]
    rd, sga, revenue = ctx.annual_flow(flows["rd"]), ctx.annual_flow(flows["sga"]), ctx.annual_flow(flows["revenue"])
    if not rd:
        ctx.gap("rd_not_reported", "No R&D expense is tagged; technology is valued at zero in methods A and B.")
    methods = [_capitalised(ctx, rd, sga), _replacement(ctx, rd, sga), _relief_from_royalty(ctx, revenue)]

    rules = dict(zip(SCENARIOS, ctx.p_triple("intangible.selection")))
    ok = [m for m in methods if m.status == "ok" and m.value is not None]
    selected, chosen = {}, {}
    for s in SCENARIOS:
        if not ok:
            selected[s], chosen[s] = 0.0, "none"
            continue
        ranked = sorted(ok, key=lambda m: getattr(m.value, s))
        pick = _RULES[rules[s]](ranked)
        selected[s], chosen[s] = getattr(pick.value, s), pick.key
    if not ok:
        ctx.gap("intangibles_unvalued", "No intangible method had enough history; intangibles are carried at zero.")
    return Intangibles(methods=methods, selected=Range(**selected), selection=rules, selected_method=chosen)
