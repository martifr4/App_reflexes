"""Deterministic pricing engine. The language model never produces a price: only this code does.

Input: a QuoteRequest (material, thickness, quantity, part geometry, processes...).
Output: an Estimate with a low/high range, a confidence level, the assumptions used, and a
cost breakdown. When information is missing, `priced` is False and `missing` says what to ask.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from .config import ClientConfig

CONFIDENCE_ORDER = ["low", "medium", "high"]


@dataclass
class PartGeometry:
    """One distinct part (flat pattern). Lengths in mm, area in mm²."""
    name: str = "part"
    cut_length_mm: float = 0.0
    pierces: int = 0
    bbox_w_mm: float = 0.0
    bbox_h_mm: float = 0.0
    area_mm2: float = 0.0           # net area (outer contour minus holes)
    bends: int | None = None        # from the DXF bend layer, if present
    source: str = "dxf"             # "dxf" = measured from a drawing; "described" = from the customer's words
    warnings: list[str] = field(default_factory=list)


@dataclass
class QuoteRequest:
    material: str | None = None             # key in config.materials
    thickness_mm: float | None = None
    quantity: int | None = None             # units of each part
    parts: list[PartGeometry] = field(default_factory=list)
    processes: list[str] = field(default_factory=lambda: ["laser"])
    bends_per_part: int | None = None       # overrides DXF bends when the customer states it
    weld_minutes_per_part: float | None = None
    finish: str | None = None               # key in config.finishes
    deadline_working_days: float | None = None
    unpriced_files: list[str] = field(default_factory=list)   # STEP/PDF/DWG/images: need a human


@dataclass
class Note:
    code: str
    params: dict = field(default_factory=dict)


@dataclass
class Estimate:
    priced: bool
    currency: str = "EUR"
    low: float | None = None
    high: float | None = None
    point: float | None = None
    per_unit_point: float | None = None
    confidence: str | None = None          # high / medium / low
    needs_review: bool = True
    missing: list[str] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)   # assumptions and reasons, as codes
    breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def interpolate(table: dict[float, float], x: float) -> float | None:
    """Linear interpolation in a {thickness: value} table. None outside the table's range."""
    pts = sorted((float(k), float(v)) for k, v in table.items())
    if not pts or x < pts[0][0] - 1e-9 or x > pts[-1][0] + 1e-9:
        return None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1] if abs(x - pts[-1][0]) < 1e-9 else pts[0][1]


def _discount(cfg: ClientConfig, qty: int) -> float:
    d = 0.0
    for step in sorted(cfg.pricing.quantity_discounts, key=lambda s: s.from_):
        if qty >= step.from_:
            d = step.discount
    return d


def _rush(cfg: ClientConfig, days: float | None) -> float:
    if days is None:
        return 0.0
    for r in sorted(cfg.pricing.rush, key=lambda r: r.under_days):
        if days < r.under_days:
            return r.surcharge
    return 0.0


def _lower(conf: str, to: str) -> str:
    return conf if CONFIDENCE_ORDER.index(conf) <= CONFIDENCE_ORDER.index(to) else to


def estimate(cfg: ClientConfig, req: QuoteRequest) -> Estimate:
    cur = cfg.pricing.currency
    notes: list[Note] = []
    missing = []
    if not req.material:
        missing.append("material")
    if not req.thickness_mm:
        missing.append("thickness")
    if not req.quantity:
        missing.append("quantity")
    if not req.parts:
        missing.append("drawing")
    if missing:
        notes += [Note("unpriced_file", {"file": f}) for f in req.unpriced_files]
        return Estimate(priced=False, currency=cur, missing=missing, notes=notes)

    if req.material not in cfg.materials:
        return Estimate(priced=False, currency=cur, notes=[Note("material_not_listed", {"material": req.material})])
    mat = cfg.materials[req.material]
    t = float(req.thickness_mm)
    qty = int(req.quantity)

    cut_rate = interpolate(mat.cut_per_m, t)
    pierce_rate = interpolate(mat.pierce_each, t)
    if cut_rate is None or pierce_rate is None:
        return Estimate(priced=False, currency=cur, notes=[Note("thickness_out_of_range", {"thickness": t})])

    processes = set(req.processes or ["laser"])
    confidence = "high"
    needs_review = False
    offered = set(cfg.client.processes_offered)
    for p in sorted(processes - offered):
        notes.append(Note("process_not_priced", {"process": p}))
        needs_review = True
        confidence = _lower(confidence, "low")

    # --- per part type costs
    parts_out = []
    material_total = processing_total = setup_total = 0.0
    total_mass_kg = total_area_m2 = 0.0
    max_w, max_h = cfg.client.max_sheet_mm
    for part in req.parts:
        if part.source != "dxf":
            confidence = _lower(confidence, "medium")
            notes.append(Note("geometry_described", {"part": part.name}))
        for w in part.warnings:
            notes.append(Note("geometry_warning", {"part": part.name, "warning": w}))
            confidence = _lower(confidence, "medium")
        long_side, short_side = max(part.bbox_w_mm, part.bbox_h_mm), min(part.bbox_w_mm, part.bbox_h_mm)
        if long_side > max(max_w, max_h) or short_side > min(max_w, max_h):
            notes.append(Note("part_too_large", {"part": part.name, "w": part.bbox_w_mm, "h": part.bbox_h_mm}))
            needs_review = True
            confidence = _lower(confidence, "low")

        basis_mm2 = part.bbox_w_mm * part.bbox_h_mm if cfg.pricing.material_basis == "bbox" else part.area_mm2
        mass_kg = basis_mm2 / 1e6 * (t / 1000) * mat.density_kg_m3 * mat.scrap_factor
        net_mass_kg = part.area_mm2 / 1e6 * (t / 1000) * mat.density_kg_m3
        material = mass_kg * mat.price_per_kg
        cutting = part.cut_length_mm / 1000 * cut_rate
        piercing = part.pierces * pierce_rate

        bending = 0.0
        bend_setup = 0.0
        if "bending" in processes:
            bends = req.bends_per_part if req.bends_per_part is not None else part.bends
            if bends is None:
                notes.append(Note("bends_unknown", {"part": part.name}))
                needs_review = True
                confidence = _lower(confidence, "low")
            elif cfg.bending is None or t > cfg.bending.max_thickness_mm:
                notes.append(Note("bending_out_of_range", {"thickness": t}))
                needs_review = True
                confidence = _lower(confidence, "low")
            elif bends > 0:
                per_bend = interpolate(cfg.bending.per_bend, t) or max(cfg.bending.per_bend.values())
                bending = bends * per_bend
                bend_setup = cfg.bending.setup_per_part_type
                if req.bends_per_part is None:
                    notes.append(Note("bends_from_drawing", {"part": part.name, "bends": bends}))

        welding = 0.0
        if "welding" in processes:
            if req.weld_minutes_per_part is None or cfg.welding is None:
                notes.append(Note("welding_needs_review", {}))
                needs_review = True
                confidence = _lower(confidence, "low")
            else:
                welding = req.weld_minutes_per_part / 60 * cfg.welding.per_hour

        processing = cutting + piercing + bending + welding
        material_total += material * qty
        processing_total += processing * qty
        setup_total += cfg.pricing.programming_per_part_type + bend_setup
        total_mass_kg += net_mass_kg * qty
        total_area_m2 += part.area_mm2 / 1e6 * qty
        parts_out.append({
            "name": part.name, "source": part.source,
            "cut_length_m": round(part.cut_length_mm / 1000, 3), "pierces": part.pierces,
            "bbox_mm": [round(part.bbox_w_mm, 1), round(part.bbox_h_mm, 1)],
            "net_area_m2": round(part.area_mm2 / 1e6, 4), "net_mass_kg": round(net_mass_kg, 3),
            "per_unit": {"material": round(material, 2), "cutting": round(cutting, 2),
                         "piercing": round(piercing, 2), "bending": round(bending, 2),
                         "welding": round(welding, 2)},
        })

    # --- finish
    finish_cost = 0.0
    if req.finish and req.finish != "none":
        f = cfg.finishes.get(req.finish)
        if f is None:
            notes.append(Note("finish_not_priced", {"finish": req.finish}))
            needs_review = True
            confidence = _lower(confidence, "medium")
        else:
            finish_cost = f.per_m2 * total_area_m2 * f.sides + f.per_kg * total_mass_kg + f.setup

    discount = _discount(cfg, qty)
    rush = _rush(cfg, req.deadline_working_days)
    cost = material_total + processing_total * (1 - discount) + setup_total + finish_cost
    price = cost * (1 + cfg.pricing.margin)
    price *= 1 + rush
    if discount:
        notes.append(Note("quantity_discount", {"discount": discount}))
    if rush:
        notes.append(Note("rush_surcharge", {"surcharge": rush, "days": req.deadline_working_days}))
    if req.deadline_working_days is None:
        notes.append(Note("standard_lead_time", {}))
    if price < cfg.pricing.minimum_order:
        notes.append(Note("minimum_order", {"minimum": cfg.pricing.minimum_order}))
        price = cfg.pricing.minimum_order
    for f in req.unpriced_files:
        notes.append(Note("unpriced_file", {"file": f}))
        needs_review = True
        confidence = _lower(confidence, "medium")
    notes.append(Note("excludes_vat_and_delivery", {}))

    lo_m, hi_m = cfg.pricing.bands[confidence]
    low = math.floor(price * lo_m)
    high = math.ceil(price * hi_m)
    return Estimate(
        priced=True, currency=cur,
        low=float(max(low, cfg.pricing.minimum_order)), high=float(high), point=round(price, 2),
        per_unit_point=round(price / (qty * len(req.parts)), 2),
        confidence=confidence, needs_review=needs_review, notes=notes,
        breakdown={
            "material": round(material_total, 2),
            "processing_before_discount": round(processing_total, 2),
            "quantity_discount": discount,
            "setup": round(setup_total, 2),
            "finish": round(finish_cost, 2),
            "cost": round(cost, 2),
            "margin": cfg.pricing.margin,
            "rush_surcharge": rush,
            "net_mass_kg": round(total_mass_kg, 2),
            "parts": parts_out,
        },
    )
