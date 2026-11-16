"""Render the memo from a Valuation. Every number comes from the valuation object through one of
the formatters below, in a unit the checker knows how to read back."""
from __future__ import annotations

from ..params import ParamSet
from ..valuation.types import Line, Range, Valuation


def usd_m(v: float) -> str:
    s = f"${abs(v) / 1e6:,.1f}m"
    return f"-{s}" if v < 0 and s != "$0.0m" else s


def usd(v: float) -> str:
    s = f"${abs(v):,.2f}"
    return f"-{s}" if v < 0 and s != "$0.00" else s


def pct(v: float) -> str:
    return f"{v * 100:,.1f}%"


def count_m(v: float) -> str:
    return f"{v / 1e6:,.2f}m"


def bare(v) -> str:
    return f"`{v}`" if isinstance(v, str) else f"{v:g}"


def _r(r: Range, f=usd_m) -> str:
    return f"{f(r.low)} | {f(r.base)} | {f(r.high)}"


def _line_rows(lines: list[Line]) -> list[str]:
    return [f"| {x.label} | {usd_m(x.book)} | {_r(x.liquidation)} | {_r(x.going_concern)} |" for x in lines]


_HDR = ("| Line | Book | Liq. low | Liq. base | Liq. high | Repro. low | Repro. base | Repro. high |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|")


def render_memo(v: Valuation, params: ParamSet, run_id: str, model_id: str | None) -> str:
    m, mk, d, e = v.meta, v.market, v.decision, v.equity
    out: list[str] = []
    w = out.append
    w(f"# {m.name} ({m.ticker}): asset-based valuation\n")
    w(f"Run `{run_id}` | as of {m.as_of} | balance sheet {m.balance_date} | last fiscal year end {m.annual_date}  ")
    w(f"Parameters `{m.params_version}` hash `{m.params_hash}` | engine `{m.engine_version}` | model `{model_id or 'none'}`\n")

    w("## Decision\n")
    w(f"**System verdict: {d.verdict}**\n")
    for reason in d.reasons:
        w(f"- {reason}")
    w("")
    w("| Measure | Value |\n|---|---:|")
    w(f"| Market cap | {usd_m(mk.market_cap)} |")
    w(f"| Buy at or below (base reproduction value less {pct(d.margin_of_safety_required)} margin of safety) | {usd_m(d.buy_below)} |")
    w(f"| Watch at or below (base reproduction value) | {usd_m(d.watch_below)} |")
    w(f"| Low liquidation value ({'required' if d.liquidation_floor_required else 'not required'} for a buy) | {usd_m(d.liquidation_floor)} |")
    if d.implied_margin_of_safety is not None:
        w(f"| Margin of safety at the current price | {pct(d.implied_margin_of_safety)} |")
    w("")

    w("## Equity value\n")
    w("| | Low | Base | High |\n|---|---:|---:|---:|")
    w(f"| Liquidation value | {_r(e.liquidation)} |")
    w(f"| Reproduction value | {_r(e.reproduction)} |")
    w(f"| Liquidation value per share | {_r(e.liquidation_per_share, usd)} |")
    w(f"| Reproduction value per share | {_r(e.reproduction_per_share, usd)} |")
    w("")
    w("Liquidation value = tangible assets at sale haircuts minus all liabilities. "
      "Reproduction value = tangible assets at rebuild cost plus the selected intangible estimate minus all liabilities.\n")

    w("## Market value\n")
    w("| | |\n|---|---:|")
    w(f"| Close on {mk.price_date} ({mk.price_source}) | {usd(mk.price)} |")
    w(f"| Shares outstanding at {mk.shares_basic_date} | {count_m(mk.shares_basic)} |")
    w(f"| Dilution: {mk.dilution_method} | {count_m(mk.dilution_shares)} |")
    w(f"| Diluted shares | {count_m(mk.shares_diluted)} |")
    w(f"| Market cap | {usd_m(mk.market_cap)} |")
    w("")

    w("## Tangible assets\n")
    w(_HDR)
    out.extend(_line_rows(v.assets))
    t = v.assets_total
    w(f"| **Total** | {usd_m(t.book)} | {_r(t.liquidation)} | {_r(t.going_concern)} |\n")

    w("## Intangible assets (reproduction lens only)\n")
    w("| Method | Low | Base | High |\n|---|---:|---:|---:|")
    for im in v.intangibles.methods:
        if im.value is None:
            w(f"| {im.label} | not run | not run | not run |")
            continue
        w(f"| **{im.label}** | {_r(im.value)} |")
        for c in im.components:
            w(f"| - {c.label} | {_r(c.value)} |")
    w(f"| **Used in the valuation** | {_r(v.intangibles.selected)} |")
    w("")
    sel, ch = v.intangibles.selection, v.intangibles.selected_method
    w("The three methods are not averaged. Rule per scenario: "
      + "; ".join(f"{s} uses `{sel[s]}` (here `{ch[s]}`)" for s in ("low", "base", "high")) + ".\n")
    for im in v.intangibles.methods:
        for note in im.notes:
            w(f"- {im.label}: {note}")
    w("")

    w("## Liabilities and prior claims\n")
    w(_HDR)
    out.extend(_line_rows(v.liabilities))
    t = v.liabilities_total
    w(f"| **Total** | {usd_m(t.book)} | {_r(t.liquidation)} | {_r(t.going_concern)} |\n")

    notes = [(x.label, n) for x in v.assets + v.liabilities for n in x.notes]
    if notes:
        w("## Line notes\n")
        for label, n in dict.fromkeys(notes):
            w(f"- {label}: {n}")
        w("")

    if v.sensitivity:
        w("## Sensitivity\n")
        w("Base equity value when one parameter is moved to its own low or high setting and all others stay at base. Largest swings first.\n")
        w("| Parameter | Repro. at low | Repro. at high | Liq. at low | Liq. at high |\n|---|---:|---:|---:|---:|")
        for s in v.sensitivity[:12]:
            w(f"| `{s.param}` | {usd_m(s.reproduction_base_at_low)} | {usd_m(s.reproduction_base_at_high)} | "
              f"{usd_m(s.liquidation_base_at_low)} | {usd_m(s.liquidation_base_at_high)} |")
        w("")

    if v.gaps:
        w("## Gaps\n")
        w("Items this run could not measure from the fact store. They are left out of the numbers above.\n")
        for g in v.gaps:
            w(f"- `{g.key}`: {g.description}")
        w("")

    w("## Parameters used\n")
    if params.applied:
        w("Overrides applied: " + ", ".join(f"`{a}`" for a in params.applied) + "\n")
    w("| Parameter | Low | Base | High |\n|---|---:|---:|---:|")
    for name in v.params_used:
        lo, ba, hi = params.triple(name)
        w(f"| `{name}` | {bare(lo)} | {bare(ba)} | {bare(hi)} |")
    w("")

    w("## Sources\n")
    w(f"Price: `{mk.price_id}`\n")
    w("| Fact | Value | Form | Filed |\n|---|---:|---|---|")
    for fid, f in v.facts_used.items():
        val = usd_m(f.value) if f.unit == "USD" else count_m(f.value)
        w(f"| `{fid}` | {val} | {f.form} | {f.filed} |")
    w("")
    return "\n".join(out)
