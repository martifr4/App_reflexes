import json

import pytest

from valuer.journal import Journal
from valuer.memo.checker import check_run
from valuer.memo.render import render_memo
from valuer.store.store import FactStore
from valuer.valuation.engine import run_valuation

from conftest import AS_OF


@pytest.fixture
def run(home, store, params):
    journal = Journal(home)
    v = run_valuation(store, "LECO", AS_OF, "csv", params)
    run_id = journal.new_run_id("LECO", AS_OF)
    run_dir = journal.save_run(run_id, v, params, render_memo(v, params, run_id, None), None)
    return journal, run_id, run_dir


def test_clean_run_passes(run, store):
    _, _, run_dir = run
    report = check_run(run_dir, store)
    assert report.passed, report.errors
    assert report.numbers_checked > 100


def _edit(path, old, new):
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def test_altered_memo_figure_fails(run, store):
    _, _, run_dir = run
    memo = (run_dir / "memo.md").read_text()
    cap = next(l for l in memo.splitlines() if l.startswith("| Market cap")).split("|")[2].strip()
    _edit(run_dir / "memo.md", cap, "$1.0m")
    report = check_run(run_dir, store)
    assert not report.passed and any("$1.0m" in e for e in report.errors)


@pytest.mark.parametrize("prose", [
    "We think fair value is $4,321.0m.",          # a figure nobody computed
    "Revenue grew 17.5% last year.",              # a recalled statistic
    "Management guided on 2031-03-31.",           # a date from nowhere
    "See `CIK59527/us-gaap:Assets/USD/2019-12-31/0000000000-00-000000`.",  # a fact the run never used
])
def test_untraceable_prose_fails(run, store, prose):
    _, _, run_dir = run
    with open(run_dir / "memo.md", "a") as fh:
        fh.write(f"\n## Analyst note\n\n{prose}\n")
    assert not check_run(run_dir, store).passed


def test_altered_valuation_fails_recompute(run, store):
    _, _, run_dir = run
    doc = json.loads((run_dir / "valuation.json").read_text())
    doc["equity"]["reproduction"]["base"] *= 2
    (run_dir / "valuation.json").write_text(json.dumps(doc))
    report = check_run(run_dir, store)
    assert any(e.startswith("recompute: /equity/reproduction/base") for e in report.errors)


def test_altered_parameters_fail(run, store):
    _, _, run_dir = run
    doc = json.loads((run_dir / "params.json").read_text())
    doc["params"]["haircut.liquidation.receivables"]["base"] = 0.99
    (run_dir / "params.json").write_text(json.dumps(doc))
    assert not check_run(run_dir, store).passed


def test_changed_store_fact_fails(run, home):
    import pyarrow.parquet as pq
    from valuer.store.store import FACT_SCHEMA

    _, _, run_dir = run
    fid = next(k for k in json.loads((run_dir / "valuation.json").read_text())["facts_used"] if ":Assets/" in k)
    path = home / "store" / "facts" / "cik=59527.parquet"
    rows = pq.read_table(path).to_pylist()
    for r in rows:
        if r["fact_id"] == fid:
            r["value"] += 1_000_000
    FactStore(home).write_facts(59527, rows)
    report = check_run(run_dir, FactStore(home))
    assert any(e.startswith(f"fact {fid}") for e in report.errors)


def test_decision_needs_a_passing_check(run, store):
    journal, run_id, run_dir = run
    with pytest.raises(RuntimeError):
        journal.decide(run_id, "pass", "not checked yet")
    journal.save_check(run_id, check_run(run_dir, store))
    journal.decide(run_id, "pass", "Far above asset value.")
    row = journal.list()[0]
    assert row[0] == run_id and row[5] == "PASS" and row[7] == "Far above asset value."
