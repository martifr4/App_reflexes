"""Read-only tools the agents call. Each wraps deterministic code; none lets an agent write."""
from __future__ import annotations

import datetime as dt
import json
from typing import Annotated, Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from ..params import ParamSet
from ..store.store import FactStore
from ..valuation.types import Valuation
from .verify import Documents

SERVER = "valuer"
MAX_READ = 80
MAX_HITS = 40


def _text(s: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": s}]}


def _valuation_summary(v: Valuation, params: ParamSet) -> dict:
    def r(x):
        return [round(x.low), round(x.base), round(x.high)]

    def line(x):
        return {"key": x.key, "label": x.label, "book": round(x.book), "liquidation": r(x.liquidation),
                "reproduction": r(x.going_concern), "formula": x.formula, "params": x.params, "notes": x.notes}

    return {
        "units": "USD; every triple is [low, base, high] by valuation scenario",
        "company": v.meta.name, "as_of": str(v.meta.as_of), "balance_sheet_date": str(v.meta.balance_date),
        "last_fiscal_year_end": str(v.meta.annual_date),
        "assets": [line(x) for x in v.assets],
        "liabilities": [line(x) for x in v.liabilities],
        "intangibles": {
            "methods": [{"key": m.key, "status": m.status, "value": r(m.value) if m.value else None,
                         "components": {c.label: r(c.value) for c in m.components}, "formula": m.formula,
                         "params": m.params, "notes": m.notes} for m in v.intangibles.methods],
            "used": r(v.intangibles.selected), "method_used_per_scenario": v.intangibles.selected_method,
        },
        "equity": {"liquidation": r(v.equity.liquidation), "reproduction": r(v.equity.reproduction)},
        "market": {"market_cap": round(v.market.market_cap), "price": v.market.price,
                   "diluted_shares": round(v.market.shares_diluted), "dilution_method": v.market.dilution_method},
        "decision": {"verdict": v.decision.verdict, "buy_below": round(v.decision.buy_below),
                     "watch_below": round(v.decision.watch_below), "reasons": v.decision.reasons},
        "gaps": [g.model_dump() for g in v.gaps],
        "parameters": {name: dict(zip(("low", "base", "high"), params.triple(name)))
                       | ({"note": params.entries[name]["note"]} if "note" in params.entries[name] else {})
                       for name in v.params_used},
        "fact_ids_used": list(v.facts_used),
    }


def build_server(docs: Documents, store: FactStore, cik: int, as_of: dt.date,
                 valuation: Valuation | None = None, params: ParamSet | None = None):
    """An in-process MCP server and the list of tool names to allow."""

    @tool("list_documents", "List the filings you can read, with their accession numbers and lengths.", {})
    async def list_documents(args):
        rows = [{"accession": a, "form": f.form, "period_end": str(f.report_date), "filed": str(f.filed),
                 "paragraphs": len(docs.lines[a])} for a, f in docs.filings.items()]
        return _text(json.dumps(rows, indent=1))

    @tool("search_document",
          "Find paragraphs in one filing that contain every word of the query (case-insensitive, any order). "
          "Returns paragraph numbers with the start of each paragraph. Use short queries of one to three words.",
          {"accession": str, "query": str})
    async def search_document(args):
        lines = docs.lines.get(args["accession"])
        if lines is None:
            return _text(f"Unknown accession {args['accession']}. Call list_documents.")
        terms = args["query"].lower().split()
        hits = [(i, ln) for i, ln in enumerate(lines, 1) if all(t in ln.lower() for t in terms)]
        if not hits:
            return _text("No paragraph contains all of those words. Try fewer or different words.")
        out = [f"p{i}: {ln[:300]}{' ...' if len(ln) > 300 else ''}" for i, ln in hits[:MAX_HITS]]
        more = f"\n({len(hits) - MAX_HITS} more matches not shown; narrow the query.)" if len(hits) > MAX_HITS else ""
        return _text("\n".join(out) + more)

    @tool("read_paragraphs",
          f"Read consecutive paragraphs of one filing in full, up to {MAX_READ} at a time. "
          "Each table row is its own paragraph. Quote from exactly what this returns.",
          {"accession": str, "start": Annotated[int, "First paragraph number"], "count": int})
    async def read_paragraphs(args):
        lines = docs.lines.get(args["accession"])
        if lines is None:
            return _text(f"Unknown accession {args['accession']}. Call list_documents.")
        start = max(1, int(args["start"]))
        end = min(len(lines), start + min(MAX_READ, max(1, int(args["count"]))) - 1)
        return _text("\n".join(f"p{i}: {lines[i - 1]}" for i in range(start, end + 1)) or "Nothing at that position.")

    @tool("find_facts",
          "Search the company's XBRL-tagged facts by concept name fragment (e.g. 'Pension', 'Warranty'). "
          "Returns the latest value of each matching concept with its fact id, which you can cite.",
          {"name_contains": str})
    async def find_facts(args):
        facts = store.search_concepts(cik, args["name_contains"], as_of)
        if not facts:
            return _text("No tagged concept name contains that text.")
        rows = [{"fact_id": f.fact_id, "concept": f.concept, "unit": f.unit, "value": f.value,
                 "period": f"{f.period_start}..{f.period_end}" if f.period_start else str(f.period_end),
                 "form": f.form} for f in facts]
        return _text(json.dumps(rows, indent=1))

    tools = [list_documents, search_document, read_paragraphs, find_facts]

    if valuation is not None and params is not None:
        summary = json.dumps(_valuation_summary(valuation, params), indent=1)

        @tool("get_valuation",
              "The deterministic valuation under review: every asset and liability line with its formula and "
              "parameters, the intangible estimates, equity values, market value, decision, known gaps and the "
              "parameter values used.", {})
        async def get_valuation(args):
            return _text(summary)

        tools.append(get_valuation)

    server = create_sdk_mcp_server(SERVER, tools=tools)
    return server, [f"mcp__{SERVER}__{t.name}" for t in tools]
