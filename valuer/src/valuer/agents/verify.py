"""Deterministic checks on agent output. Nothing an agent returns is trusted until it passes here.

* A quote must appear verbatim in the paragraph the agent cited.
* A figure must appear inside its quote; code parses it and applies the scale.
* The stated scale needs its own verbatim evidence, and the result must be plausible in size.
* Text the agent writes in its own words must contain no digits.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ..edgar.ingest import filing_paths
from ..edgar.text import normalise
from ..raw import RawArchive
from ..store.store import Filing
from .schemas import EXTRACTION_KEYS, Evidence, Extraction

_NUMBER = re.compile(r"^\(?\s*\$?\s*(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*\)?$")
_DIGIT = re.compile(r"\d")
_ALLOWED_DIGIT_WORDS = re.compile(r"\b10-[KQ]\b")
SCALES = {"ones": 1.0, "thousands": 1e3, "millions": 1e6, "billions": 1e9}
_SCALE_WORD = {"thousands": "thousand", "millions": "million", "billions": "billion"}
MIN_QUOTE_CHARS = 12


class Documents:
    """The current filings' text, by accession. Lines are 1-based paragraphs."""

    def __init__(self, home: Path, ticker: str, filings: list[Filing]):
        self.filings = {f.accession: f for f in filings}
        archive = RawArchive(home, ticker)
        self.rel = {f.accession: filing_paths(f)[1] for f in filings}
        self.lines = {f.accession: archive.path(self.rel[f.accession]).read_text().splitlines() for f in filings}

    def check(self, ev: Evidence) -> str | None:
        """None if the quote is in the cited paragraph, else the reason it is rejected."""
        lines = self.lines.get(ev.accession)
        if lines is None:
            return f"unknown filing {ev.accession}"
        if not 1 <= ev.paragraph <= len(lines):
            return f"paragraph {ev.paragraph} is outside the document"
        quote = normalise(ev.quote)
        if len(quote) < MIN_QUOTE_CHARS:
            return "quote is too short to identify a passage"
        if quote not in normalise(lines[ev.paragraph - 1]):
            return f"quote not found verbatim in paragraph {ev.paragraph}"
        return None


def parse_number(text: str) -> float:
    m = _NUMBER.match(text.strip())
    if not m:
        raise ValueError(f"{text!r} is not a plain figure")
    v = float(m.group(1).replace(",", "") + (m.group(2) or ""))
    return -v if text.strip().startswith("(") else v


TERM_SEP = " + "


def parse_sum(number_text: str) -> float:
    """Value of a stored number_text: one figure, or several from the same quote joined by ' + '."""
    return sum(parse_number(t) for t in number_text.split(TERM_SEP))


def has_digits(text: str) -> bool:
    return bool(_DIGIT.search(_ALLOWED_DIGIT_WORDS.sub("", text)))


@dataclass
class Bounds:
    total_assets: float
    shares: float
    price: float

    def check(self, unit: str, value: float) -> str | None:
        if value < 0:
            return "negative value"
        if unit == "USD" and value > 3 * self.total_assets:
            return "larger than three times total assets; the scale is probably wrong"
        if unit == "shares" and value > self.shares:
            return "more than the shares outstanding; the scale is probably wrong"
        if unit == "USD/shares" and not 0 < value < 100 * self.price:
            return "not a plausible per-share price"
        return None


def verify_extraction(x: Extraction, analyst: str, docs: Documents, bounds: Bounds, cik: int,
                      recorded_at: dt.datetime, model_id: str) -> tuple[dict | None, str | None]:
    """(tier-2 row, None) if the extraction holds up, else (None, reason)."""
    if x.key not in EXTRACTION_KEYS or EXTRACTION_KEYS[x.key][1] != analyst:
        return None, f"{x.key!r} is not a key this analyst was asked for"
    unit = EXTRACTION_KEYS[x.key][0]
    annual = next(f for f in docs.filings.values() if f.form == "10-K")

    def row(filing: Filing, **kw) -> dict:
        ident = "|".join(str(kw.get(k)) for k in ("status", "number_text", "scale", "paragraph", "quote"))
        digest = hashlib.sha256(ident.encode()).hexdigest()[:8]
        base = dict(
            fact_id=f"T2/CIK{cik}/{x.key}/{filing.report_date}/{filing.accession}/{digest}", cik=cik, key=x.key,
            unit=unit, period_end=filing.report_date, accession=filing.accession, form=filing.form,
            filed=filing.filed, recorded_at=recorded_at, document=docs.rel[filing.accession],
            extracted_by=model_id, value=None, paragraph=None, quote=None, number_text=None, scale=None,
            scale_paragraph=None, scale_quote=None, note="" if has_digits(x.note) else x.note,
        )
        return base | kw

    if x.status == "not_disclosed":
        # An absence is a judgment about the annual report; it cannot be verified, only recorded.
        return row(annual, status="not_disclosed"), None

    if x.evidence is None or x.number_text is None or x.scale is None:
        return None, "found, but evidence, number_text or scale is missing"
    err = docs.check(x.evidence)
    if err:
        return None, err
    quote = normalise(x.evidence.quote)
    terms = [x.number_text, *x.add_number_texts]
    remaining = quote
    for t in terms:  # each figure must be in the quote, and no figure may be counted twice
        if normalise(t) not in remaining:
            return None, f"figure {t!r} is not inside the quote"
        remaining = remaining.replace(normalise(t), " ", 1)
    try:
        number = sum(parse_number(t) for t in terms)
    except ValueError as exc:
        return None, str(exc)

    scale_ev = None
    if x.scale != "ones" and _SCALE_WORD[x.scale] not in quote.lower():
        if x.scale_evidence is None:
            return None, f"scale '{x.scale}' has no supporting quote"
        if x.scale_evidence.accession != x.evidence.accession:
            return None, "scale evidence is from a different filing"
        err = docs.check(x.scale_evidence)
        if err:
            return None, f"scale evidence: {err}"
        if _SCALE_WORD[x.scale] not in normalise(x.scale_evidence.quote).lower():
            return None, f"scale evidence does not say '{_SCALE_WORD[x.scale]}'"
        scale_ev = x.scale_evidence

    value = number * SCALES[x.scale]
    err = bounds.check(unit, value)
    if err:
        return None, err
    filing = docs.filings[x.evidence.accession]
    return row(filing, status="found", value=value, paragraph=x.evidence.paragraph, quote=x.evidence.quote,
               number_text=TERM_SEP.join(terms), scale=x.scale,
               scale_paragraph=scale_ev.paragraph if scale_ev else None,
               scale_quote=scale_ev.quote if scale_ev else None), None


def reverify_tier2(ref: dict, lines: list[str]) -> str | None:
    """Re-check a stored tier-2 fact against the filing text (used by the checker)."""
    if ref.get("status") != "found":
        return None
    p = ref["paragraph"]
    if not 1 <= p <= len(lines) or normalise(ref["quote"]) not in normalise(lines[p - 1]):
        return "quote is no longer in the cited paragraph"
    if any(normalise(t) not in normalise(ref["quote"]) for t in ref["number_text"].split(TERM_SEP)):
        return "figure is not inside the quote"
    if abs(parse_sum(ref["number_text"]) * SCALES[ref["scale"]] - ref["value"]) > 1e-6 * max(1.0, abs(ref["value"])):
        return "stored value does not equal the quoted figure times its scale"
    return None
