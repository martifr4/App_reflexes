import datetime as dt

import pytest
import yaml

from valuer.params import ParamError, load_params
from valuer.store.store import FactStore, make_fact_id
from valuer.valuation.intangibles import _amortised_stock
from valuer.valuation.types import Range

from conftest import PARAMS_DIR


def test_range_arithmetic_is_per_scenario():
    assets, liabilities = Range(low=50, base=80, high=100), Range(low=70, base=60, high=60)
    assert assets - liabilities == Range(low=-20, base=20, high=40)
    assert assets * Range(low=0.5, base=1, high=1) == Range(low=25, base=80, high=100)


def test_amortised_stock_straight_line():
    # 3-year life: this year's spend counts in full, last year's 2/3, the year before 1/3
    assert _amortised_stock([90, 60, 30, 999], 3) == pytest.approx(90 + 40 + 10)


def test_params_overrides_and_hash(tmp_path):
    base, leco = load_params(PARAMS_DIR), load_params(PARAMS_DIR, ticker="LECO")
    assert base.triple("intangible.sga_includes_rd")[1] == 0
    assert leco.triple("intangible.sga_includes_rd")[1] == 1
    assert leco.applied == ["company:LECO"] and base.hash != leco.hash
    assert base.with_base("tax.rate", 0.3).hash != base.hash


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("tax.rate"),
    lambda p: p.update({"haircut.liquidation.typo": {"value": 1}}),
    lambda p: p.update({"tax.rate": {"low": 0.2, "base": 0.2}}),
])
def test_params_reject_missing_unknown_and_partial(tmp_path, mutate):
    doc = yaml.safe_load((PARAMS_DIR / "params.yaml").read_text())
    mutate(doc["params"])
    (tmp_path / "params.yaml").write_text(yaml.safe_dump(doc))
    with pytest.raises(ParamError):
        load_params(tmp_path)


def _row(val, accn, filed, end="2024-12-31"):
    return {"fact_id": make_fact_id(1, "us-gaap", "Assets", "USD", None, end, accn), "cik": 1,
            "taxonomy": "us-gaap", "concept": "Assets", "unit": "USD", "period_start": None,
            "period_end": dt.date.fromisoformat(end), "value": val, "accession": accn, "form": "10-K",
            "fy": 2024, "fp": "FY", "filed": dt.date.fromisoformat(filed)}


def test_store_is_point_in_time(tmp_path):
    store = FactStore(tmp_path)
    store.write_facts(1, [_row(100.0, "a-1", "2025-02-20"), _row(90.0, "a-2", "2026-02-20")])  # restated a year later
    end = dt.date(2024, 12, 31)
    assert store.instant(1, "Assets", end, dt.date(2025, 2, 19)) is None
    assert store.instant(1, "Assets", end, dt.date(2025, 2, 20)).value == 100.0
    assert store.instant(1, "Assets", end, dt.date(2026, 2, 19)).value == 100.0
    assert store.instant(1, "Assets", end, dt.date(2026, 2, 20)).value == 90.0


def test_prices_are_append_only(tmp_path):
    store, d = FactStore(tmp_path), dt.date(2026, 1, 5)
    assert store.add_prices("X", "csv", [(d, 10.0)]) == 1
    assert store.add_prices("X", "csv", [(d, 11.0), (d + dt.timedelta(days=1), 12.0)]) == 1
    assert store.price_asof("X", d, "csv").close == 10.0
