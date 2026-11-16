import datetime as dt

import pytest

from valuer.store.store import FactStore
from valuer.valuation.engine import ExcludedIndustry, run_valuation

from conftest import AS_OF


def test_lines_reconcile_to_reported_totals(store, params):
    v = run_valuation(store, "LECO", AS_OF, "csv", params)
    bd = v.meta.balance_date
    assert bd == dt.date(2026, 9, 30) and v.meta.annual_date == dt.date(2025, 12, 31)
    assert v.assets_total.book == pytest.approx(store.instant(v.meta.cik, "Assets", bd, AS_OF).value)
    assert v.liabilities_total.book == pytest.approx(store.instant(v.meta.cik, "Liabilities", bd, AS_OF).value)


def test_scenarios_are_ordered_and_identities_hold(store, params):
    v = run_valuation(store, "LECO", AS_OF, "csv", params)
    for r in (v.equity.liquidation, v.equity.reproduction, v.intangibles.selected):
        assert r.low <= r.base <= r.high
    for s in ("low", "base", "high"):
        assert getattr(v.equity.liquidation, s) == pytest.approx(
            getattr(v.assets_total.liquidation, s) - getattr(v.liabilities_total.liquidation, s))
        assert getattr(v.equity.reproduction, s) == pytest.approx(
            getattr(v.assets_total.going_concern, s) + getattr(v.intangibles.selected, s)
            - getattr(v.liabilities_total.going_concern, s))
    assert v.market.market_cap == pytest.approx(v.market.price * v.market.shares_diluted)
    assert {m.status for m in v.intangibles.methods} == {"ok"}
    # goodwill and book intangibles never carry value: they are replaced by the estimates
    for line in v.assets:
        if line.key in ("goodwill", "book_intangibles"):
            assert line.going_concern.high == 0 and line.liquidation.high == 0


def test_every_line_cites_facts_or_params(store, params):
    v = run_valuation(store, "LECO", AS_OF, "csv", params)
    for line in v.assets + v.liabilities:
        assert line.facts or line.params, line.key
        assert set(line.facts) <= set(v.facts_used) and set(line.params) <= set(v.params_used)


def test_valuation_is_deterministic(store, params, home):
    a = run_valuation(store, "LECO", AS_OF, "csv", params)
    b = run_valuation(FactStore(home), "LECO", AS_OF, "csv", params)
    assert a.model_dump_json() == b.model_dump_json()


def test_as_of_hides_later_filings(store, params):
    # The FY2025 10-K was filed on 2026-02-25. The day before, only the Q3 2025 balance sheet is visible.
    store.add_prices("LECO", "csv", [(dt.date(2026, 2, 24), 100.0), (dt.date(2026, 2, 25), 100.0)])
    before = run_valuation(store, "LECO", dt.date(2026, 2, 24), "csv", params)
    after = run_valuation(store, "LECO", dt.date(2026, 2, 25), "csv", params)
    assert before.meta.balance_date == dt.date(2025, 9, 30) and before.meta.annual_date == dt.date(2024, 12, 31)
    assert after.meta.balance_date == dt.date(2025, 12, 31)
    assert all(f.filed <= dt.date(2026, 2, 24) for f in before.facts_used.values())


def test_decision_rule(store, params):
    v = run_valuation(store, "LECO", AS_OF, "csv", params)
    base = v.equity.reproduction.base
    # Re-price the shares so the market cap lands in each band.
    for cap, expected in ((base * 1.5, "PASS"), (base * 0.9, "WATCH"), (base * 0.5, "WATCH")):
        s = FactStore(store.root.parent)
        s.add_prices("LECO", f"t{expected}{int(cap)}", [(AS_OF, cap / v.market.shares_diluted)])
        assert run_valuation(s, "LECO", AS_OF, f"t{expected}{int(cap)}", params).decision.verdict == expected
    # With the liquidation floor switched off, a deep enough discount to reproduction value is a BUY.
    loose = params.with_base("decision.buy_requires_liquidation_floor", 0)
    s = FactStore(store.root.parent)
    s.add_prices("LECO", "cheap", [(AS_OF, base * 0.5 / v.market.shares_diluted)])
    assert run_valuation(s, "LECO", AS_OF, "cheap", loose).decision.verdict == "BUY"


def test_financials_are_refused(store, params):
    store.write_entity({"cik": 59527, "ticker": "LECO", "name": "x", "sic": 6022, "sic_description": "bank",
                        "fiscal_year_end": "1231"})
    with pytest.raises(ExcludedIndustry):
        run_valuation(store, "LECO", AS_OF, "csv", params)
