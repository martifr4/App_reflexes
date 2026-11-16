"""The valuation: a pure function of (fact store, ticker, as-of date, price source, parameters).

Same inputs give the same output, which is what lets the checker recompute a saved run.
"""
from __future__ import annotations

import datetime as dt

from .. import ENGINE_VERSION
from ..edgar.ingest import EXCLUDED_SIC
from ..params import ParamSet
from ..store.store import FactStore
from .assets import value_assets
from .context import Ctx, MappingError
from .intangibles import value_intangibles
from .liabilities import value_liabilities
from .types import (Decision, Equity, Line, Market, Meta, Range, Sensitivity, Totals, Valuation)

SCENARIOS = ("low", "base", "high")


class ExcludedIndustry(RuntimeError):
    pass


def _totals(lines: list[Line]) -> Totals:
    return Totals(
        book=sum(x.book for x in lines),
        liquidation=sum((x.liquidation for x in lines), Range.const(0.0)),
        going_concern=sum((x.going_concern for x in lines), Range.const(0.0)),
    )


def _market(ctx: Ctx, price_source: str) -> Market:
    m = ctx.mapping["shares"]
    stale_days = int(ctx.p_triple("market.max_price_stale_days")[1])
    px = ctx.store.price_asof(ctx.entity.ticker, ctx.as_of, price_source, stale_days)

    basic = ctx.store.latest_instant(ctx.cik, m["cover"], ctx.as_of, unit="shares", taxonomy="dei")
    if basic is None:
        basic = ctx.store.latest_instant(ctx.cik, m["balance_sheet"], ctx.as_of, unit="shares")
    if basic is None:
        raise MappingError(f"{ctx.entity.ticker}: no share count in the fact store (multiple share classes?)")
    ctx.record(basic)

    adj = ctx.store.latest_duration(ctx.cik, m["dilution_adjustment"], ctx.as_of, "shares")
    if adj is not None:
        ctx.record(adj)
        dilution, method = adj.value, "reported dilution adjustment (latest period)"
    else:
        dil = ctx.store.latest_duration(ctx.cik, m["weighted_diluted"], ctx.as_of, "shares")
        bas = dil and ctx.store.duration(ctx.cik, m["weighted_basic"], dil.period_start, dil.period_end, ctx.as_of, "shares")
        if dil and bas:
            ctx.record(dil, bas)
            dilution, method = max(0.0, dil.value - bas.value), "weighted diluted less weighted basic shares (latest period)"
        else:
            dilution, method = 0.0, "none available"
            ctx.gap("dilution", "No dilution data in the XBRL company facts; basic shares are used.")
    # Tier-2: option and award counts read from the footnotes allow a treasury-stock calculation at
    # the current price. The larger of that and the reported figure is used.
    opts, strike, awards = (ctx.tier2(k) for k in ("options_outstanding", "options_wavg_exercise_price", "unvested_stock_awards"))
    found = lambda t: t is not None and t.status == "found" and t.value is not None  # noqa: E731
    have_options = found(opts) and found(strike)
    options_settled = have_options or (opts is not None and opts.status == "not_disclosed")
    if options_settled and (found(awards) or have_options):
        from_options = opts.value * max(0.0, 1 - strike.value / px.close) if have_options else 0.0
        own = from_options + (awards.value if found(awards) else 0.0)
        if own >= dilution:
            dilution = own
            method = "treasury-stock method at the current price plus unvested awards (from footnotes)"
        else:
            method += "; larger than the footnote-based calculation"
        if have_options:
            ctx.gap("dilution_strike", "Options are valued at their average exercise price, which understates dilution "
                                       "when some grants are in the money and others are not. Convertibles are not included.")
    else:
        ctx.gap("dilution_method", "Dilution uses the company's reported figure at its own average share price. "
                                   "A treasury-stock calculation at today's price, and convertibles, need the option "
                                   "and award tables from the footnotes.")
    diluted = basic.value + dilution
    return Market(price=px.close, price_date=px.date, price_source=px.source, price_id=px.price_id,
                  shares_basic=basic.value, shares_basic_date=basic.period_end, dilution_shares=dilution,
                  dilution_method=method, shares_diluted=diluted, market_cap=px.close * diluted)


def _decide(ctx: Ctx, equity: Equity, market: Market) -> Decision:
    mos = float(ctx.p_triple("decision.margin_of_safety")[1])
    floor_required = bool(ctx.p_triple("decision.buy_requires_liquidation_floor")[1])
    base, cap = equity.reproduction.base, market.market_cap
    buy_below, floor = (1 - mos) * base, equity.liquidation.low
    reasons = []
    under_buy = base > 0 and cap <= buy_below
    under_floor = cap <= floor
    reasons.append("Market cap is at or below the buy threshold." if under_buy
                   else "Market cap is above the buy threshold (base reproduction value less the margin of safety).")
    if floor_required:
        reasons.append("Market cap is at or below the low liquidation value." if under_floor
                       else "Market cap is above the low liquidation value, so the liquidation floor does not protect the price.")
    if under_buy and (under_floor or not floor_required):
        verdict = "BUY"
    elif base > 0 and cap <= base:
        verdict = "WATCH"
        reasons.append("Market cap is at or below base reproduction value.")
    else:
        verdict = "PASS"
        reasons.append("Market cap is above base reproduction value.")
    return Decision(verdict=verdict, margin_of_safety_required=mos, buy_below=buy_below, watch_below=base,
                    liquidation_floor=floor, liquidation_floor_required=floor_required,
                    implied_margin_of_safety=(1 - cap / base) if base > 0 else None, reasons=reasons)


def _compute(store: FactStore, ticker: str, as_of: dt.date, price_source: str, params: ParamSet,
             knowledge_time: dt.datetime) -> Valuation:
    entity = store.resolve(ticker)
    if entity.sic in EXCLUDED_SIC:
        raise ExcludedIndustry(f"{ticker}: SIC {entity.sic} ({entity.sic_description}) is a financial company; "
                               "the asset-based method does not apply.")
    ctx = Ctx(store, entity, as_of, params, knowledge_time)
    assets = value_assets(ctx)
    intangibles = value_intangibles(ctx)
    liabilities = value_liabilities(ctx, assets)
    a, l = _totals(assets), _totals(liabilities)
    market = _market(ctx, price_source)
    liq = a.liquidation - l.liquidation
    rep = a.going_concern + intangibles.selected - l.going_concern
    equity = Equity(liquidation=liq, reproduction=rep,
                    liquidation_per_share=liq.map(lambda v: v / market.shares_diluted),
                    reproduction_per_share=rep.map(lambda v: v / market.shares_diluted))
    decision = _decide(ctx, equity, market)
    meta = Meta(ticker=entity.ticker, cik=entity.cik, name=entity.name, sic=entity.sic, as_of=as_of,
                knowledge_time=knowledge_time,
                balance_date=ctx.balance_date, annual_date=ctx.annual_date, price_source=price_source,
                params_version=params.version, params_hash=params.hash, engine_version=ENGINE_VERSION)
    return Valuation(meta=meta, assets=assets, assets_total=a, liabilities=liabilities, liabilities_total=l,
                     intangibles=intangibles, equity=equity, market=market, decision=decision, gaps=ctx.gaps,
                     facts_used=dict(sorted(ctx.facts_used.items())), params_used=sorted(ctx.params_used))


def _sensitivity(store: FactStore, base_run: Valuation, params: ParamSet) -> list[Sensitivity]:
    """One parameter at a time: set its base to its own low, then its own high; all others at base."""
    m = base_run.meta
    out = []
    for name in base_run.params_used:
        lo, ba, hi = params.triple(name)
        if lo == ba == hi:
            continue
        runs = [_compute(store, m.ticker, m.as_of, m.price_source, params.with_base(name, v), m.knowledge_time)
                for v in (lo, hi)]
        r_lo, r_hi = (r.equity.reproduction.base for r in runs)
        l_lo, l_hi = (r.equity.liquidation.base for r in runs)
        swing = max(abs(r_hi - r_lo), abs(l_hi - l_lo))
        if swing > 0:
            out.append(Sensitivity(param=name, reproduction_base_at_low=r_lo, reproduction_base_at_high=r_hi,
                                   liquidation_base_at_low=l_lo, liquidation_base_at_high=l_hi, swing=swing))
    return sorted(out, key=lambda s: -s.swing)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0)


def run_valuation(store: FactStore, ticker: str, as_of: dt.date, price_source: str, params: ParamSet,
                  knowledge_time: dt.datetime | None = None) -> Valuation:
    """``knowledge_time`` (UTC) pins which tier-2 facts count; it defaults to now and is saved with the run."""
    v = _compute(store, ticker, as_of, price_source, params, knowledge_time or utc_now())
    return v.model_copy(update={"sensitivity": _sensitivity(store, v, params)})


def run_with_overrides(store: FactStore, base_run: Valuation, params: ParamSet, overrides: dict[str, float]) -> Valuation:
    """The same run with some parameters' base values replaced (the bear scenario). No sensitivity table."""
    for name, value in overrides.items():
        params = params.with_base(name, value)
    m = base_run.meta
    return _compute(store, m.ticker, m.as_of, m.price_source, params, m.knowledge_time)
