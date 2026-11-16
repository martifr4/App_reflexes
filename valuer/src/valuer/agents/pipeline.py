"""The agent-assisted run.

    1. deterministic valuation from what the store already holds (shows the gaps)
    2. asset analyst and liabilities analyst read the filings      -> verified by code -> tier-2 facts
    3. deterministic valuation again, now using those facts
    4. bear-case agent attacks the result                           -> verified by code -> bear scenario re-run
    5. memo, checker, journal

Agents only ever produce candidates. Code decides what is accepted, and everything rejected is
kept in findings.json with the reason.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import math
from pathlib import Path
from typing import Awaitable, Callable

from ..edgar.ingest import ensure_filing_docs, filing_paths
from ..journal import Journal
from ..memo.checker import check_run
from ..memo.render import render_memo
from ..params import ParamSet
from ..raw import collect_sources
from ..store.store import FactStore
from ..valuation.engine import run_valuation, run_with_overrides, utc_now
from ..valuation.types import Valuation
from . import prompts
from .runtime import AgentResult, run_agent
from .schemas import AnalystReport, BearReport, Evidence, Extraction
from .tools import build_server
from .verify import Bounds, Documents, has_digits, verify_extraction

Runner = Callable[..., Awaitable[AgentResult]]
_SEVERITY = {"high": 0, "medium": 1, "low": 2}


def _evidence(ev: dict, docs: Documents, ticker: str) -> dict:
    return {"quote": ev["quote"], "source": f"{ticker}/{docs.rel[ev['accession']]}:{ev['paragraph']}"}


def _process_analyst(analyst: str, result: AgentResult, docs: Documents, bounds: Bounds, v: Valuation,
                     recorded_at: dt.datetime) -> tuple[list[dict], dict]:
    """Verify one analyst's report. Returns (tier-2 rows to store, findings entry)."""
    report = AnalystReport.model_validate(result.output)
    model_id = ",".join(result.models)
    rows, accepted, rejected = [], [], []
    seen: set[str] = set()
    for x in report.extractions:
        if x.key in seen:
            rejected.append({"key": x.key, "reason": "duplicate key in the report"})
            continue
        seen.add(x.key)
        row, reason = verify_extraction(x, analyst, docs, bounds, v.meta.cik, recorded_at, model_id)
        if row is None:
            rejected.append({"key": x.key, "reason": reason})
        else:
            rows.append(row)
            accepted.append({"key": x.key, "status": row["status"], "fact_id": row["fact_id"],
                             "note": "" if has_digits(x.note) else x.note})

    known = {ln.key for ln in v.assets + v.liabilities} | {g.key for g in v.gaps} | {"general"}
    observations, rejected_obs = [], []
    for o in report.observations:
        reason = docs.check(Evidence(**o.evidence.model_dump()))
        if reason is None and has_digits(o.statement):
            reason = "statement contains digits"
        if reason:
            rejected_obs.append({"statement": o.statement, "reason": reason})
        else:
            observations.append({"line": o.line if o.line in known else "general", "direction": o.direction,
                                 "statement": o.statement} | _evidence(o.evidence.model_dump(), docs, v.meta.ticker))
    entry = {"model": model_id, "turns": result.turns, "cost_usd": result.cost_usd, "extractions": accepted,
             "rejected_extractions": rejected, "observations": observations, "rejected_observations": rejected_obs}
    return rows, entry


def _override_ok(name: str, value: float, v: Valuation, params: ParamSet) -> str | None:
    if name not in v.params_used:
        return "not a parameter this valuation used"
    lo, ba, hi = params.triple(name)
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lo, ba, hi)):
        return "not a numeric parameter"
    if name.startswith(("decision.", "mapping.", "market.")):
        return "decision rules and controls are not open to override"
    if not math.isfinite(value) or value < 0:
        return "value must be a non-negative number"
    if name.startswith("haircut.") and value > 2:
        return "a haircut above two is not credible"
    if value > 10 * max(abs(lo), abs(hi), 1):
        return "value is far outside the parameter's own range"
    return None


def _process_bear(result: AgentResult, docs: Documents, store: FactStore, v: Valuation, params: ParamSet) -> dict:
    report = BearReport.model_validate(result.output)
    attacks, rejected, overrides, rejected_overrides = [], [], {}, []
    for a in sorted(report.attacks, key=lambda a: _SEVERITY[a.severity]):
        reason, support = None, {}
        if has_digits(a.claim):
            reason = "claim contains digits"
        elif a.evidence is not None:
            reason = docs.check(a.evidence)
            support = _evidence(a.evidence.model_dump(), docs, v.meta.ticker) if reason is None else {}
        elif a.fact_id:
            f = store.fact_by_id(a.fact_id) if a.fact_id.startswith(("CIK", "T2/")) else None
            if f is None or f.cik != v.meta.cik or f.filed > v.meta.as_of:
                reason = f"fact {a.fact_id} is not in the store for this company and date"
            else:
                support = {"fact_id": a.fact_id}
        else:
            reason = "no evidence given"
        if reason:
            rejected.append({"target": a.target, "claim": a.claim, "reason": reason})
            continue
        entry = {"target": a.target, "severity": a.severity, "claim": a.claim} | support
        if a.override is not None:
            why = _override_ok(a.override.param, a.override.base, v, params)
            if why is None and a.override.param in overrides:
                why = "a stronger attack already overrides this parameter"
            if why:
                rejected_overrides.append({"param": a.override.param, "reason": why})
            else:
                overrides[a.override.param] = a.override.base
                entry["override_param"] = a.override.param
        attacks.append(entry)

    bear = {"model": ",".join(result.models), "turns": result.turns, "cost_usd": result.cost_usd,
            "summary": "" if has_digits(report.summary) else report.summary,
            "attacks": attacks, "rejected_attacks": rejected, "rejected_overrides": rejected_overrides,
            "overrides": [{"param": k, "original_base": params.triple(k)[1], "proposed_base": val}
                          for k, val in overrides.items()]}
    if overrides:
        scenario = run_with_overrides(store, v, params, overrides)
        bear["scenario"] = {"equity": json.loads(scenario.equity.model_dump_json()),
                            "verdict": scenario.decision.verdict}
    return bear


async def analyse(home: Path, store: FactStore, journal: Journal, ticker: str, as_of: dt.date, price_source: str,
                  params: ParamSet, model: str, runner: Runner = run_agent) -> tuple[str, Path, Valuation, dict]:
    """Run the full agent-assisted valuation. Returns (run_id, run_dir, valuation, findings)."""
    entity = store.resolve(ticker)
    filings = ensure_filing_docs(store, home, entity, as_of)
    if not filings:
        raise RuntimeError(f"{ticker}: no annual report filed on or before {as_of}")
    docs = Documents(home, entity.ticker, filings)
    fmt = dict(name=entity.name, ticker=entity.ticker, as_of=as_of)

    # 1-2. preliminary valuation, then the two analysts in parallel
    prelim = run_valuation(store, ticker, as_of, price_source, params)
    total_assets = sum(x.book for x in prelim.assets)
    bounds = Bounds(total_assets=total_assets, shares=prelim.market.shares_basic, price=prelim.market.price)
    server, allowed = build_server(docs, store, entity.cik, as_of, prelim, params)
    asset_res, liab_res = await asyncio.gather(
        runner("asset_analyst", prompts.ASSET_ANALYST, prompts.ANALYST_TASK.format(**fmt), server, allowed, AnalystReport, model),
        runner("liabilities_analyst", prompts.LIABILITIES_ANALYST, prompts.ANALYST_TASK.format(**fmt), server, allowed, AnalystReport, model),
    )
    recorded_at = utc_now()
    findings: dict = {"analysts": {}}
    for analyst, res in (("asset", asset_res), ("liabilities", liab_res)):
        rows, entry = _process_analyst(analyst, res, docs, bounds, prelim, recorded_at)
        store.add_tier2(entity.cik, rows)
        findings["analysts"][analyst] = entry

    # 3. final valuation, pinned to the moment the tier-2 facts were recorded
    v = run_valuation(store, ticker, as_of, price_source, params, knowledge_time=recorded_at)

    # 4. bear case on the final valuation, in a fresh agent that never saw the analysts' work
    server, allowed = build_server(docs, store, entity.cik, as_of, v, params)
    bear_res = await runner("bear_case", prompts.BEAR, prompts.BEAR_TASK.format(**fmt), server, allowed, BearReport, model)
    findings["bear"] = _process_bear(bear_res, docs, store, v, params)

    # 5. memo, archive, check
    models = sorted({m for r in (asset_res, liab_res, bear_res) for m in r.models})
    model_id = ",".join(models)
    run_id = journal.new_run_id(entity.ticker, as_of)
    sources = collect_sources(home, entity.ticker, [r for f in filings for r in filing_paths(f)], price_source)
    memo = render_memo(v, params, run_id, model_id, findings=findings, sources=sources)
    transcript = asset_res.transcript + liab_res.transcript + bear_res.transcript
    run_dir = journal.save_run(run_id, v, params, memo, model_id, sources=sources, findings=findings, transcript=transcript)
    journal.save_check(run_id, check_run(run_dir, store, home))
    return run_id, run_dir, v, findings


__all__ = ["analyse", "Extraction"]
