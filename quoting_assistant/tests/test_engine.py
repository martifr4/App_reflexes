import pytest

from app.pricing.config import load_client_config
from app.pricing.engine import PartGeometry, QuoteRequest, estimate, interpolate


@pytest.fixture(scope="module")
def cfg():
    return load_client_config("demo_shop")


def square(side=100.0, holes=0, bends=None, source="dxf"):
    return PartGeometry(name="sq", cut_length_mm=4 * side, pierces=1 + holes,
                        bbox_w_mm=side, bbox_h_mm=side, area_mm2=side * side,
                        bends=bends, source=source)


def codes(est):
    return {n.code for n in est.notes}


def test_config_loads_and_is_marked_sample(cfg):
    assert cfg.client.name == "Taller Demo SL"
    assert cfg.client.sample_values is True
    assert "steel" in cfg.materials


def test_interpolate():
    t = {1: 1.0, 3: 3.0}
    assert interpolate(t, 2) == pytest.approx(2.0)
    assert interpolate(t, 1) == 1.0 and interpolate(t, 3) == 3.0
    assert interpolate(t, 0.5) is None and interpolate(t, 4) is None


def test_missing_information_gives_no_price(cfg):
    est = estimate(cfg, QuoteRequest(material="steel"))
    assert not est.priced and est.low is None
    assert set(est.missing) == {"thickness", "quantity", "drawing"}


def test_point_price_matches_hand_calculation(cfg):
    # 100 x 100 mm, 3 mm steel, 100 units. Per part: material 0.01 m² x 3 mm x 7850 x 1.10 x 1.05 €/kg
    # = 0.2720; cutting 0.4 m x 0.60 = 0.24; 1 pierce 0.03. Total: 27.20 + 27.0 x 0.90 + 25 setup
    # = 76.50 cost, x 1.30 margin = 99.45
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100, parts=[square()]))
    assert est.priced and est.confidence == "high" and not est.needs_review
    assert est.point == pytest.approx(99.45, abs=0.01)
    assert est.low <= est.point <= est.high
    assert "quantity_discount" in codes(est)


def test_minimum_order(cfg):
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=1, parts=[square()]))
    assert est.point == cfg.pricing.minimum_order
    assert "minimum_order" in codes(est)


def test_rush_surcharge(cfg):
    base = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100, parts=[square()]))
    rush = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100, parts=[square()],
                                      deadline_working_days=3))
    assert rush.point == pytest.approx(base.point * 1.25, abs=0.01)


def test_stainless_costs_more_than_steel(cfg):
    req = dict(thickness_mm=3, quantity=100, parts=[square()])
    assert estimate(cfg, QuoteRequest(material="stainless_304", **req)).point > \
        estimate(cfg, QuoteRequest(material="steel", **req)).point


def test_bending_with_known_bends(cfg):
    plain = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100, parts=[square()]))
    bent = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100,
                                      parts=[square(bends=2)], processes=["laser", "bending"]))
    # 2 bends x 0.60 € x 100 x 0.90 discount + 40 € setup, all x 1.30
    assert bent.point - plain.point == pytest.approx((2 * 0.60 * 100 * 0.90 + 40) * 1.30, abs=0.01)
    assert bent.confidence == "high"


def test_bending_without_bend_count_needs_review(cfg):
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100,
                                     parts=[square()], processes=["laser", "bending"]))
    assert est.priced and est.needs_review and est.confidence == "low"
    assert "bends_unknown" in codes(est)


def test_machining_is_not_priced_by_the_bot(cfg):
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100,
                                     parts=[square()], processes=["laser", "machining"]))
    assert est.needs_review and "process_not_priced" in codes(est)


def test_thickness_out_of_range_and_unknown_material(cfg):
    assert not estimate(cfg, QuoteRequest(material="steel", thickness_mm=40, quantity=5, parts=[square()])).priced
    est = estimate(cfg, QuoteRequest(material="titanium", thickness_mm=3, quantity=5, parts=[square()]))
    assert not est.priced and "material_not_listed" in codes(est)


def test_described_geometry_lowers_confidence(cfg):
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100,
                                     parts=[square(source="described")]))
    assert est.confidence == "medium"
    lo, hi = cfg.pricing.bands["medium"]
    assert est.high >= est.point * hi - 1


def test_unpriced_file_flags_review(cfg):
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=100, parts=[square()],
                                     unpriced_files=["bracket.step"]))
    assert est.needs_review and "unpriced_file" in codes(est)


def test_part_too_large_for_machine(cfg):
    big = PartGeometry(cut_length_mm=8000, pierces=1, bbox_w_mm=3500, bbox_h_mm=500, area_mm2=1.75e6)
    est = estimate(cfg, QuoteRequest(material="steel", thickness_mm=3, quantity=2, parts=[big]))
    assert est.needs_review and "part_too_large" in codes(est)
