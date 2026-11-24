"""Read a flat-pattern DXF and measure what pricing needs: cut length, pierces, bounding box,
net area and bends (lines on a layer named like BEND / PLEG / DOBL).

Assumes one part per file, drawn 1:1. Units come from $INSUNITS (mm if unset, with a warning).
"""
from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf import bbox as ezbbox
from ezdxf import path as ezpath

from .engine import PartGeometry

CUT_TYPES = {"LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE"}
BEND_LAYER_HINTS = ("BEND", "PLEG", "DOBL", "PLIEG", "FOLD")
IGNORE_LAYER_HINTS = ("DIM", "COTA", "TEXT", "TEXTO", "ANNOT", "TITLE", "CAJETIN", "DEFPOINTS")
UNIT_TO_MM = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0}
FLATTEN_TOL = 0.01   # mm
JOIN_TOL = 0.05      # mm: endpoints closer than this are treated as connected


def _is_bend_layer(layer: str) -> bool:
    return any(h in layer.upper() for h in BEND_LAYER_HINTS)


def _is_ignored_layer(layer: str) -> bool:
    return any(h in layer.upper() for h in IGNORE_LAYER_HINTS)


def _entities(msp):
    """Model-space entities with block references exploded."""
    for e in msp:
        if e.dxftype() == "INSERT":
            yield from e.virtual_entities()
        else:
            yield e


def _polygon_area(pts) -> float:
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def _chain(pieces: list[list[tuple[float, float]]]):
    """Join open polylines end to end into contours. Returns (closed_loops, open_chains)."""
    def near(a, b):
        return math.dist(a, b) <= JOIN_TOL

    remaining = [p[:] for p in pieces]
    closed, open_ = [], []
    while remaining:
        chain = remaining.pop(0)
        grown = True
        while grown and not near(chain[0], chain[-1]):
            grown = False
            for i, p in enumerate(remaining):
                if near(chain[-1], p[0]):
                    chain += p[1:]
                elif near(chain[-1], p[-1]):
                    chain += p[::-1][1:]
                elif near(chain[0], p[-1]):
                    chain = p[:-1] + chain
                elif near(chain[0], p[0]):
                    chain = p[::-1][:-1] + chain
                else:
                    continue
                remaining.pop(i)
                grown = True
                break
        (closed if len(chain) > 2 and near(chain[0], chain[-1]) else open_).append(chain)
    return closed, open_


def parse_dxf(path: str | Path, name: str | None = None) -> PartGeometry:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    warnings: list[str] = []
    insunits = doc.header.get("$INSUNITS", 0)
    scale = UNIT_TO_MM.get(insunits)
    if scale is None:
        warnings.append(f"unsupported drawing units ($INSUNITS={insunits}); assumed mm")
        scale = 1.0

    cut_len = 0.0
    bends = 0
    has_bend_layer = False
    loops: list[list[tuple[float, float]]] = []
    pieces: list[list[tuple[float, float]]] = []
    cut_entities = []
    for e in _entities(msp):
        kind = e.dxftype()
        layer = e.dxf.get("layer", "0")
        if kind not in CUT_TYPES or _is_ignored_layer(layer):
            continue
        if _is_bend_layer(layer):
            has_bend_layer = True
            if kind in ("LINE", "LWPOLYLINE", "POLYLINE"):
                bends += 1
            continue
        try:
            p = ezpath.make_path(e)
        except (TypeError, ValueError):
            warnings.append(f"could not read a {kind} entity")
            continue
        pts = [(v.x * scale, v.y * scale) for v in p.flattening(FLATTEN_TOL)]
        if len(pts) < 2:
            continue
        cut_len += sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        cut_entities.append(e)
        if math.dist(pts[0], pts[-1]) <= JOIN_TOL and len(pts) > 2:
            loops.append(pts)
        else:
            pieces.append(pts)

    if not cut_entities:
        raise ValueError("no cutting geometry found in the DXF")

    chained, open_chains = _chain(pieces)
    loops += chained
    if open_chains:
        warnings.append(f"{len(open_chains)} open contour(s): the drawing may have gaps")

    box = ezbbox.extents(cut_entities, fast=False)
    w = (box.extmax.x - box.extmin.x) * scale
    h = (box.extmax.y - box.extmin.y) * scale

    if insunits == 0 and not 5 <= max(w, h) <= 6000:
        warnings.append("drawing units not set and the size looks unusual; assumed mm")

    # Net area: largest loop is the outer contour; loops inside its bounding box are holes.
    areas = sorted(((_polygon_area(lp), lp) for lp in loops), key=lambda t: -t[0])
    net = 0.0
    if areas:
        outer_area, outer = areas[0]
        xs, ys = [p[0] for p in outer], [p[1] for p in outer]
        net = outer_area
        for a, lp in areas[1:]:
            cx = sum(p[0] for p in lp) / len(lp)
            cy = sum(p[1] for p in lp) / len(lp)
            if min(xs) <= cx <= max(xs) and min(ys) <= cy <= max(ys):
                net -= a
            else:
                warnings.append("more than one separate part in the file; priced as one")
                net += a
    else:
        warnings.append("no closed outer contour; area taken from the bounding box")
        net = w * h

    return PartGeometry(
        name=name or Path(path).stem,
        cut_length_mm=round(cut_len, 2),
        pierces=len(loops) + len(open_chains),
        bbox_w_mm=round(w, 2),
        bbox_h_mm=round(h, 2),
        area_mm2=round(net, 2),
        bends=bends if has_bend_layer else None,
        source="dxf",
        warnings=sorted(set(warnings)),
    )
