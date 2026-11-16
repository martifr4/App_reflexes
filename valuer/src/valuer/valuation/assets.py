"""Tangible assets, line by line: book value x haircut, in both lenses.

The lines always sum to reported total assets: whatever is not mapped lands in a residual line.
"""
from __future__ import annotations

from .context import Ctx, Found, MappingError
from .types import Line, Range


def _line(ctx: Ctx, key: str, label: str, book: float, haircut: str, facts: list[str],
          notes: list[str] | None = None, formula: str = "book x haircut") -> Line:
    pl, pg = f"haircut.liquidation.{haircut}", f"haircut.going_concern.{haircut}"
    return Line(
        key=key, label=label, book=book,
        liquidation=ctx.p(pl) * book, going_concern=ctx.p(pg) * book,
        facts=facts, params=[pl, pg], formula=formula, notes=notes or [],
    )


def _stale_note(f: Found) -> list[str]:
    return [f"Not in the latest balance sheet; uses the value at {f.date.isoformat()}."] if f.stale else []


def _inventory(ctx: Ctx, spec: dict) -> list[Line]:
    net = ctx.lookup(spec["net"])
    if net is None or net.value == 0:
        return []
    lines: list[Line] = []
    parts = {k: ctx.lookup(spec[k], at=net.date) for k in ("finished_goods", "work_in_process", "raw_materials")}
    found = {k: v for k, v in parts.items() if v is not None and v.value > 0}
    total_parts = sum(v.value for v in found.values())
    if found and total_parts > 0:
        haircuts = {"finished_goods": "inventory_fg", "work_in_process": "inventory_wip", "raw_materials": "inventory_rm"}
        labels = {"finished_goods": "Inventory: finished goods", "work_in_process": "Inventory: work in process",
                  "raw_materials": "Inventory: raw materials"}
        exact = abs(total_parts - net.value) <= 1e-6 * abs(net.value)
        for k, v in found.items():
            lines.append(_line(
                ctx, f"inventory_{k}", labels[k], net.value * v.value / total_parts, haircuts[k],
                v.ids + net.ids,
                notes=_stale_note(net) + ([] if exact else ["Reported components do not sum to net inventory; allocated pro rata."]),
                formula="net inventory x component share x haircut",
            ))
    else:
        lines.append(_line(ctx, "inventory", "Inventory (no component split)", net.value,
                           "inventory_unclassified", net.ids, notes=_stale_note(net)))

    lifo = ctx.lookup(spec["lifo_reserve"], at=net.date)
    if lifo is not None and lifo.value > 0:
        # The reserve is the excess of current cost over LIFO carrying value. It realises at the
        # same blended fraction as the inventory it belongs to; no separate assumption.
        blend_l = Range(**{s: sum(getattr(x.liquidation, s) for x in lines) / net.value for s in ("low", "base", "high")})
        blend_g = Range(**{s: sum(getattr(x.going_concern, s) for x in lines) / net.value for s in ("low", "base", "high")})
        lines.append(Line(
            key="lifo_reserve", label="LIFO reserve (off balance sheet)", book=0.0,
            liquidation=blend_l * lifo.value, going_concern=blend_g * lifo.value,
            facts=lifo.ids, params=sorted({p for x in lines for p in x.params}),
            formula="LIFO reserve x blended inventory realisation",
            notes=["Not carried on the balance sheet. Any liquidation gain is taxed in the liabilities section."],
        ))
    return lines


def _ppe(ctx: Ctx, spec: dict) -> list[Line]:
    net = ctx.lookup(spec["net"])
    if net is None or net.value == 0:
        return []
    # Component detail is usually only in the 10-K, so shares are measured at one consistent date.
    for date in dict.fromkeys([net.date, ctx.annual_date]):
        net_c = ctx.lookup(spec["net"], at=date)
        gross = ctx.lookup(spec["gross"], at=date)
        bldg = ctx.lookup(spec["buildings"], at=date)
        if net_c and gross and bldg:
            break
    else:
        return [_line(ctx, "ppe", "Property, plant and equipment (no component split)", net.value,
                      "ppe_unclassified", net.ids, notes=_stale_note(net))]

    land = ctx.lookup(spec["land"], at=date)
    cip = ctx.lookup(spec["cip"], at=date)
    land_v, cip_v = (land.value if land else 0.0), (cip.value if cip else 0.0)
    dep_gross = gross.value - land_v - cip_v
    dep_net = net_c.value - land_v - cip_v
    if dep_gross <= 0 or dep_net < 0 or bldg.value > dep_gross:
        return [_line(ctx, "ppe", "Property, plant and equipment (no component split)", net.value,
                      "ppe_unclassified", net.ids, notes=_stale_note(net) + ["Component detail inconsistent; not split."])]

    b_share = dep_net * (bldg.value / dep_gross) / net_c.value
    shares = {
        "land": (land_v / net_c.value, "Land", "land", land),
        "cip": (cip_v / net_c.value, "Construction in progress", "cip", cip),
        "buildings": (b_share, "Buildings and improvements", "buildings", bldg),
        "equipment": (dep_net / net_c.value - b_share, "Machinery, equipment and other", "equipment", gross),
    }
    note = (
        f"Split uses component detail at {date.isoformat()}. Land and construction in progress are not depreciated; "
        "accumulated depreciation is spread over buildings and equipment in proportion to gross cost."
    )
    out = []
    for key, (share, label, haircut, f) in shares.items():
        if share <= 0:
            continue
        ids = (f.ids if f else []) + gross.ids + net_c.ids + net.ids
        out.append(_line(ctx, f"ppe_{key}", f"PP&E: {label}", net.value * share, haircut,
                         list(dict.fromkeys(ids)), notes=[note], formula="net PP&E x component share x haircut"))
    return out


def value_assets(ctx: Ctx) -> list[Line]:
    spec = ctx.mapping["assets"]
    total = ctx.require(spec["total"], "total assets")
    current_total = ctx.lookup(spec["current_total"], allow_stale=False)

    current: list[Line] = []
    noncurrent: list[Line] = []
    for item in spec["lines"]:
        f = ctx.lookup(item["options"])
        if f is None or f.value == 0:
            continue
        (current if item["class"] == "current" else noncurrent).append(
            _line(ctx, item["key"], item["label"], f.value, item["haircut"], f.ids, notes=_stale_note(f))
        )
        if item.get("gap_if_present") == "fair_value_levels":
            ctx.gap("fair_value_levels", "Securities are held but the fair-value level split is not in the XBRL company facts; "
                                         "a single securities haircut is used.")
    current += _inventory(ctx, spec["inventory"])
    noncurrent = _ppe(ctx, spec["ppe"]) + noncurrent

    tol = ctx.p("mapping.residual_tolerance").base * total.value

    def residual(key: str, label: str, amount: float, haircut: str, facts: list[str]) -> Line | None:
        if amount < -tol:
            raise MappingError(
                f"{ctx.entity.ticker}: mapped {label.lower()} exceed the reported total by {-amount:,.0f}. "
                "A concept is probably counted twice in line_items.yaml."
            )
        if amount == 0:
            return None
        return _line(ctx, key, label, amount, haircut, facts, formula="(reported total - mapped lines) x haircut",
                     notes=["Residual: everything not mapped to a line above."])

    lines = current + noncurrent
    if current_total is not None:
        r1 = residual("other_current", "Other current assets", current_total.value - sum(x.book for x in current),
                      "other_current", current_total.ids)
        r2 = residual("other_noncurrent", "Other non-current assets",
                      total.value - current_total.value - sum(x.book for x in noncurrent),
                      "other_noncurrent", total.ids + current_total.ids)
        lines = current + ([r1] if r1 else []) + noncurrent + ([r2] if r2 else [])
    else:
        r = residual("other_noncurrent", "Other assets", total.value - sum(x.book for x in lines),
                     "other_noncurrent", total.ids)
        lines += [r] if r else []
    return lines
