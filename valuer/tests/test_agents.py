"""Agent layer, offline: a fake runner stands in for Claude so the verification code is what's tested."""
import asyncio
import datetime as dt
import json

import pytest

from valuer.agents import pipeline
from valuer.agents.runtime import AgentResult
from valuer.agents.schemas import Evidence, Extraction
from valuer.agents.verify import Bounds, Documents, verify_extraction
from valuer.edgar.ingest import current_filings, save_filing
from valuer.edgar.text import html_to_lines
from valuer.journal import Journal
from valuer.memo.checker import check_run
from valuer.raw import RawArchive

from conftest import AS_OF

K10 = "0000059527-26-000006"
HTML_10K = """<html><body><div style="display:none">hidden xbrl header 999</div>
<p>Pension note.</p>
<p>(In thousands)</p>
<table><tr><td><p>Benefit obligations at end of year</p></td><td>7,300</td><td>86,779</td><td>7,862</td></tr></table>
<p>Stock options</p>
<table><tr><td>Balance at end of year</td><td>621,683</td><td>150.63</td></tr>
<tr><td>Balance at end of year</td><td>241,774</td><td>210.59</td></tr></table>
<p>The Company is a co-defendant in asbestos lawsuits and cannot estimate a range of possible losses.</p>
</body></html>"""


@pytest.fixture
def docs(home, store):
    archive = RawArchive(home, "LECO")
    for f in current_filings(store, 59527, AS_OF):
        save_filing(archive, f, (HTML_10K if f.accession == K10 else "<p>Quarterly update with nothing new.</p>").encode())
    return Documents(home, "LECO", current_filings(store, 59527, AS_OF))


def _line(docs, text):
    return next(i for i, ln in enumerate(docs.lines[K10], 1) if text in ln)


def test_text_keeps_rows_whole_and_drops_hidden(docs):
    lines = docs.lines[K10]
    assert "Benefit obligations at end of year 7,300 86,779 7,862" in lines
    assert not any("hidden" in ln for ln in lines)
    assert html_to_lines(HTML_10K) == lines  # deterministic


def _x(docs, **kw):
    p = _line(docs, "Benefit obligations")
    base = dict(key="pension_benefit_obligation", status="found", number_text="7,300", add_number_texts=["86,779"],
                scale="thousands", evidence=Evidence(accession=K10, paragraph=p, quote="Benefit obligations at end of year 7,300 86,779"),
                scale_evidence=Evidence(accession=K10, paragraph=_line(docs, "(In thousands)"), quote="(In thousands)"),
                note="Adds the two plan groups.")
    return Extraction(**(base | kw))


BOUNDS = Bounds(total_assets=4e9, shares=5.4e7, price=280.0)
KT = dt.datetime(2026, 11, 16, 12)


def test_verified_sum(docs):
    row, err = verify_extraction(_x(docs), "liabilities", docs, BOUNDS, 59527, KT, "m")
    assert err is None and row["value"] == pytest.approx(94_079_000) and row["number_text"] == "7,300 + 86,779"


@pytest.mark.parametrize("change,reason", [
    (dict(number_text="7,301", add_number_texts=[]), "not inside the quote"),
    (dict(add_number_texts=["7,300"]), "not inside the quote"),  # same figure counted twice
    (dict(evidence=Evidence(accession=K10, paragraph=2, quote="Benefit obligations at end of year 7,300")), "not found verbatim"),
    (dict(scale_evidence=None), "no supporting quote"),
    (dict(scale="billions", scale_evidence=None), "no supporting quote"),
    (dict(key="options_outstanding"), "not a key this analyst"),
])
def test_bad_extractions_rejected(docs, change, reason):
    row, err = verify_extraction(_x(docs, **change), "liabilities", docs, BOUNDS, 59527, KT, "m")
    assert row is None and reason in err


def _canned(docs):
    opt, aw = _line(docs, "621,683"), _line(docs, "241,774")
    asset = {"extractions": [
        {"key": "options_outstanding", "status": "found", "number_text": "621,683", "scale": "ones",
         "evidence": {"accession": K10, "paragraph": opt, "quote": "Balance at end of year 621,683 150.63"}},
        {"key": "options_wavg_exercise_price", "status": "found", "number_text": "150.63", "scale": "ones",
         "evidence": {"accession": K10, "paragraph": opt, "quote": "Balance at end of year 621,683 150.63"}},
        {"key": "unvested_stock_awards", "status": "found", "number_text": "241,774", "scale": "ones",
         "evidence": {"accession": K10, "paragraph": aw, "quote": "Balance at end of year 241,774 210.59"}}],
        "observations": [{"line": "general", "direction": "lowers_value", "statement": "Made up claim with 42 in it.",
                          "evidence": {"accession": K10, "paragraph": aw, "quote": "Balance at end of year 241,774"}}]}
    liab = {"extractions": [_x(docs).model_dump(),
                            {"key": "contingent_possible_loss", "status": "not_disclosed", "note": "No estimate given."},
                            {"key": "guarantee_max_exposure", "status": "found", "number_text": "999", "scale": "ones",
                             "evidence": {"accession": K10, "paragraph": 1, "quote": "a quote that is not there"}}],
            "observations": [{"line": "other_liabilities", "direction": "lowers_value",
                              "statement": "Asbestos exposure has no estimate.",
                              "evidence": {"accession": K10, "paragraph": _line(docs, "asbestos"),
                                           "quote": "co-defendant in asbestos lawsuits"}}]}
    bear = {"summary": "Equipment is worth less.", "attacks": [
        {"target": "haircut.going_concern.equipment", "severity": "high", "claim": "Plants are closing.",
         "evidence": {"accession": K10, "paragraph": _line(docs, "asbestos"), "quote": "co-defendant in asbestos lawsuits"},
         "override": {"param": "haircut.going_concern.equipment", "base": 0.7}},
        {"target": "decision", "severity": "high", "claim": "Lower the bar.", "fact_id": "CIK59527/nope",
         "override": {"param": "decision.margin_of_safety", "base": 0.0}}]}
    return {"asset_analyst": asset, "liabilities_analyst": liab, "bear_case": bear}


def test_pipeline_end_to_end_offline(home, store, params, docs):
    canned = _canned(docs)

    async def fake_runner(name, system, prompt, server, allowed, schema, model):
        assert all(t.startswith("mcp__valuer__") for t in allowed)
        return AgentResult(output=schema.model_validate(canned[name]).model_dump(), models=["fake-model"])

    journal = Journal(home)
    run_id, run_dir, v, findings = asyncio.run(
        pipeline.analyse(home, store, journal, "LECO", AS_OF, "csv", params, "fake-model", runner=fake_runner))

    a, l, b = findings["analysts"]["asset"], findings["analysts"]["liabilities"], findings["bear"]
    assert len(a["extractions"]) == 3 and a["rejected_observations"][0]["reason"] == "statement contains digits"
    assert [x["key"] for x in l["rejected_extractions"]] == ["guarantee_max_exposure"]
    assert [o["param"] for o in b["overrides"]] == ["haircut.going_concern.equipment"]
    assert b["rejected_attacks"][0]["target"] == "decision"
    assert b["scenario"]["equity"]["reproduction"]["base"] < v.equity.reproduction.base

    assert "treasury-stock" in v.market.dilution_method
    pension = next(x for x in v.liabilities if x.key == "pension_repricing")
    assert pension.liquidation.low == pytest.approx(0.01 * 12 * 94_079_000)
    report = json.loads((run_dir / "check.json").read_text())
    assert report["passed"], report["errors"]
    assert report["quotes_checked"] >= 3
    assert (run_dir / "transcript.jsonl").exists() and json.loads((run_dir / "sources.json").read_text())


def test_checker_catches_tampered_quote_and_filing(home, store, params, docs):
    async def fake_runner(name, system, prompt, server, allowed, schema, model):
        return AgentResult(output=schema.model_validate(_canned(docs)[name]).model_dump(), models=["fake-model"])

    _, run_dir, _, _ = asyncio.run(pipeline.analyse(home, store, Journal(home), "LECO", AS_OF, "csv", params, "m", runner=fake_runner))
    memo = run_dir / "memo.md"
    memo.write_text(memo.read_text().replace("co-defendant in asbestos lawsuits", "co-defendant in many asbestos lawsuits", 1))
    assert any("quote fails verification" in e for e in check_run(run_dir, store, home).errors)

    memo.write_text(memo.read_text().replace("co-defendant in many asbestos lawsuits", "co-defendant in asbestos lawsuits", 1))
    assert check_run(run_dir, store, home).passed
    txt = next((home / "raw" / "LECO" / "filings" / K10).glob("*.txt"))
    txt.write_text(txt.read_text().replace("7,300", "7,900"))
    errors = check_run(run_dir, store, home).errors
    assert any("has changed since the run" in e for e in errors) and any("no longer in the cited paragraph" in e for e in errors)
