"""Download one company's SEC data into its raw folder and load it into the fact store.

Parsing is separate from fetching so tests run offline.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from ..raw import RawArchive
from ..store.store import Entity, Filing, FactStore, make_fact_id
from .client import COMPANYFACTS_URL, SUBMISSIONS_URL, TICKERS_URL, EdgarClient
from .text import html_to_lines

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


# ------------------------------------------------------------------ filing documents
def filing_paths(filing: Filing) -> tuple[str, str]:
    """Paths of a filing's .htm and derived .txt, relative to the company's raw folder."""
    base = f"filings/{filing.accession}/{filing.primary_document}"
    return base, base.rsplit(".", 1)[0] + ".txt"


def save_filing(archive: RawArchive, filing: Filing, html: bytes | None = None) -> Path:
    """Archive a filing's .htm (when given) and write the .txt derived from it."""
    htm_rel, txt_rel = filing_paths(filing)
    what = f"{filing.form} for the period ending {filing.report_date}, filed {filing.filed}"
    if html is None:
        html = archive.path(htm_rel).read_bytes()
    else:
        archive.save(htm_rel, html, filing.url, f"{what}, as filed")
    text = ("\n".join(html_to_lines(html.decode("utf-8", errors="replace"))) + "\n").encode()
    txt = archive.path(txt_rel)
    if txt.exists() and txt.read_bytes() == text:
        return txt
    return archive.save(txt_rel, text, f"derived from {htm_rel}",
                        f"{what}, as plain text; line numbers are the paragraph numbers in citations")


def current_filings(store: FactStore, cik: int, as_of: dt.date) -> list[Filing]:
    """The latest 10-K visible on ``as_of`` and every 10-Q filed after it."""
    visible = [f for f in store.filings(cik) if f.filed <= as_of and not f.form.endswith("/A")]
    annual = [f for f in visible if f.form == "10-K"]
    if not annual:
        return []
    k = max(annual, key=lambda f: f.filed)
    return [k] + sorted((f for f in visible if f.form == "10-Q" and f.filed > k.filed), key=lambda f: f.filed)


def ensure_filing_docs(store: FactStore, home: Path, entity: Entity, as_of: dt.date,
                       client: EdgarClient | None = None) -> list[Filing]:
    """Make sure the filings relevant on ``as_of`` are in the raw folder; download any missing."""
    archive = RawArchive(home, entity.ticker)
    filings = current_filings(store, entity.cik, as_of)
    for f in filings:
        if archive.path(filing_paths(f)[0]).exists():
            save_filing(archive, f)  # no download; refreshes the text only if the converter changed
        else:
            client = client or EdgarClient()
            save_filing(archive, f, client.get(f.url))
    return filings


def ingest(store: FactStore, home: Path, client: EdgarClient, ticker: str) -> dict:
    ticker = ticker.upper()
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    tickers = client.get(TICKERS_URL)
    shared = Path(home) / "raw" / "_shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / f"company_tickers.{today}.json").write_bytes(tickers)
    cik = next((int(r["cik_str"]) for r in json.loads(tickers).values() if r["ticker"].upper() == ticker), None)
    if cik is None:
        raise KeyError(f"Ticker {ticker} not found in SEC company_tickers.json")

    archive = RawArchive(home, ticker)
    sub_url, facts_url = SUBMISSIONS_URL.format(cik=cik), COMPANYFACTS_URL.format(cik=cik)
    sub, facts = client.get(sub_url), client.get(facts_url)
    archive.save(f"sec/submissions.{today}.json", sub, sub_url, "SEC filing index and company profile (SIC code, fiscal year end)")
    archive.save(f"sec/companyfacts.{today}.json", facts, facts_url, "Every XBRL-tagged fact the company has filed; source of the XBRL fact store")
    info = load_documents(store, ticker, json.loads(sub), json.loads(facts))
    docs = ensure_filing_docs(store, home, store.resolve(ticker), dt.date.today(), client)
    return info | {"filings": [f"{f.form} filed {f.filed}" for f in docs], "raw_dir": str(archive.dir)}
