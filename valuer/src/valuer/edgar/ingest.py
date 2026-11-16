"""Turn EDGAR JSON into fact-store rows. Parsing is separate from fetching so tests run offline."""
from __future__ import annotations

import datetime as dt

from ..store.store import FactStore, make_fact_id
from .client import EdgarClient

# Banks, insurers, REITs and other financial vehicles: the asset-based method does not apply.
EXCLUDED_SIC = range(6000, 6800)


def _d(s: str | None) -> dt.date | None:
    return dt.date.fromisoformat(s) if s else None


def parse_companyfacts(doc: dict) -> list[dict]:
    cik = int(doc["cik"])
    rows: dict[str, dict] = {}
    for taxonomy, concepts in doc.get("facts", {}).items():
        for concept, body in concepts.items():
            for unit, items in body.get("units", {}).items():
                for it in items:
                    if it.get("val") is None or not it.get("filed") or not it.get("accn"):
                        continue
                    fid = make_fact_id(cik, taxonomy, concept, unit, it.get("start"), it["end"], it["accn"])
                    rows[fid] = {
                        "fact_id": fid,
                        "cik": cik,
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "unit": unit,
                        "period_start": _d(it.get("start")),
                        "period_end": _d(it["end"]),
                        "value": float(it["val"]),
                        "accession": it["accn"],
                        "form": it.get("form") or "",
                        "fy": it.get("fy"),
                        "fp": it.get("fp"),
                        "filed": _d(it["filed"]),
                    }
    return list(rows.values())


def parse_entity(sub: dict, ticker: str) -> dict:
    return {
        "cik": int(sub["cik"]),
        "ticker": ticker.upper(),
        "name": sub.get("name", ""),
        "sic": int(sub.get("sic") or 0),
        "sic_description": sub.get("sicDescription", ""),
        "fiscal_year_end": sub.get("fiscalYearEnd", ""),
    }


def parse_filings(sub: dict) -> list[dict]:
    cik = int(sub["cik"])
    r = sub["filings"]["recent"]
    out = []
    for i, form in enumerate(r["form"]):
        if form not in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
            continue
        accn = r["accessionNumber"][i]
        doc = r["primaryDocument"][i]
        out.append(
            {
                "cik": cik,
                "accession": accn,
                "form": form,
                "filed": _d(r["filingDate"][i]),
                "report_date": _d(r["reportDate"][i] or None),
                "primary_document": doc,
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{doc}",
            }
        )
    return out


def load_documents(store: FactStore, ticker: str, submissions: dict, companyfacts: dict) -> dict:
    """Write one company's entity, filing index and XBRL facts into the store."""
    entity = parse_entity(submissions, ticker)
    store.write_entity(entity)
    store.write_filings(entity["cik"], parse_filings(submissions))
    n = store.write_facts(entity["cik"], parse_companyfacts(companyfacts))
    return {"cik": entity["cik"], "name": entity["name"], "sic": entity["sic"], "facts": n}


def ingest(store: FactStore, client: EdgarClient, ticker: str) -> dict:
    cik = client.cik_for_ticker(ticker)
    return load_documents(store, ticker, client.submissions(cik), client.companyfacts(cik))
