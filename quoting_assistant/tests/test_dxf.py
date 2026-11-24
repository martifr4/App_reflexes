import math
from pathlib import Path

import ezdxf
import pytest

from app.pricing.config import load_client_config
from app.pricing.dxf import parse_dxf
from app.pricing.engine import QuoteRequest, estimate
from samples.make_samples import SAMPLES

PI = math.pi
SAMPLES_DIR: Path


@pytest.fixture(scope="module", autouse=True)
def regenerate_samples(tmp_path_factory):
    """Build the samples fresh from the generator (in a temp dir, so the repo copies stay untouched)."""
    global SAMPLES_DIR
    SAMPLES_DIR = tmp_path_factory.mktemp("samples")
    for name, fn in SAMPLES.items():
        fn(SAMPLES_DIR / name)


def rel(x):
    return pytest.approx(x, rel=1e-3)  # 0.1 %: arcs are flattened at 0.01 mm


def test_base_plate():
    g = parse_dxf(SAMPLES_DIR / "placa_base_200x150.dxf")
    assert g.cut_length_mm == rel(2 * (200 + 150) + 4 * PI * 12)
    assert g.pierces == 5
    assert (g.bbox_w_mm, g.bbox_h_mm) == (200, 150)
    assert g.area_mm2 == rel(200 * 150 - 4 * PI * 6 ** 2)
    assert g.bends is None and g.warnings == []      # text on layer COTES is ignored


def test_bracket_chains_loose_lines_and_arcs_and_counts_bends():
    g = parse_dxf(SAMPLES_DIR / "escaire_plegat.dxf")
    outer = 2 * (120 - 10) + 2 * (80 - 10) + 2 * PI * 5
    assert g.cut_length_mm == rel(outer + 2 * PI * 8)          # bend line not counted as cut
    assert g.pierces == 3
    assert g.area_mm2 == rel(120 * 80 - (4 - PI) * 25 - 2 * PI * 16)
    assert g.bends == 1 and g.warnings == []


def test_flange():
    g = parse_dxf(SAMPLES_DIR / "brida_160.dxf")
    assert g.cut_length_mm == rel(PI * (160 + 80 + 6 * 10))
    assert g.pierces == 8
    assert (g.bbox_w_mm, g.bbox_h_mm) == (160, 160)
    assert g.area_mm2 == rel(PI / 4 * (160 ** 2 - 80 ** 2 - 6 * 10 ** 2))


def test_inch_drawing_is_converted(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 1
    doc.modelspace().add_lwpolyline([(0, 0), (4, 0), (4, 2), (0, 2)], close=True)
    f = tmp_path / "inch.dxf"
    doc.saveas(f)
    g = parse_dxf(f)
    assert (g.bbox_w_mm, g.bbox_h_mm) == (pytest.approx(101.6), pytest.approx(50.8))


def test_gap_in_contour_is_flagged(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, 2))     # 2 mm gap
    f = tmp_path / "gap.dxf"
    doc.saveas(f)
    assert any("open contour" in w for w in parse_dxf(f).warnings)


def test_block_references_are_exploded(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    blk = doc.blocks.new("HOLE")
    blk.add_circle((0, 0), 5)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
    msp.add_blockref("HOLE", (50, 50))
    f = tmp_path / "blk.dxf"
    doc.saveas(f)
    assert parse_dxf(f).pierces == 2


def test_empty_drawing_raises(tmp_path):
    doc = ezdxf.new()
    f = tmp_path / "empty.dxf"
    doc.saveas(f)
    with pytest.raises(ValueError):
        parse_dxf(f)


def test_samples_price_end_to_end():
    cfg = load_client_config("demo_shop")
    bracket = parse_dxf(SAMPLES_DIR / "escaire_plegat.dxf")
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=2, quantity=50,
                                     parts=[bracket], processes=["laser", "bending"]))
    assert est.priced and est.confidence == "high" and not est.needs_review
    assert any(n.code == "bends_from_drawing" for n in est.notes)
