"""Reconcile a saved run against the fact store and the raw filings. Any mismatch fails the run.

1. Every fact and price the valuation cites still exists in the store with the same value.
   Figures read from filing text are re-derived from their quote, and the quote is looked up
   again in the raw filing.
2. Recomputing the valuation (and the bear scenario) from the store and the saved parameters
   reproduces the saved one.
3. Every number, date, link, quote and backticked identifier in the memo traces to the valuation,
   the parameters, the findings, the store or the raw filings. A figure that matches nothing is an
   error, whoever wrote it.
4. The filing documents listed as sources are byte-identical to when the run was made.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import re
from pathlib import Path

from pydantic import BaseModel

from ..edgar.text import normalise
from ..params import REQUIRED, ParamSet
from ..store.store import FactStore
from ..valuation.engine import run_valuation, run_with_overrides
from ..valuation.types import Valuation

_CODE = re.compile(r"`([^`]*)`")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_QUOTE_LINE = re.compile(r'^\s*> "(.*)" — `([^`:]+):(\d+)`\s*$', re.M)
_ALLOWED_WORDS = re.compile(r"\b10-[KQ](?:/A)?(?![\w])")
_NUMBER = re.compile(
    r"(?<![\w.,$])(?P<sign>[-−])?(?P<cur>\$)?(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?(?P<suf>bn|m|%)?(?![\w])"
)
_SCALE = {"m": 1e6, "bn": 1e9, "%": 0.01, None: 1.0}


class CheckReport(BaseModel):
    passed: bool
    errors: list[str]
    facts_checked: int
    numbers_checked: int
    quotes_checked: int = 0


def _leaves(obj, numbers: list[float], strings: list[str]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        numbers.append(float(obj))
    elif isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, dict):
        for k, val in obj.items():
            strings.append(str(k))
            _leaves(val, numbers, strings)
    elif isinstance(obj, (list, tuple)):
        for val in obj:
            _leaves(val, numbers, strings)


def _diff(a, b, path: str, out: list[str]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"recompute: {path}/{k} present on one side only")
            else:
                _diff(a[k], b[k], f"{path}/{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"recompute: {path} has {len(a)} items saved, {len(b)} recomputed")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                _diff(x, y, f"{path}[{i}]", out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6):
            out.append(f"recompute: {path} saved {a!r}, recomputed {b!r}")
    elif a != b:
        out.append(f"recompute: {path} saved {a!r}, recomputed {b!r}")


class _RawText:
    """Lines of raw text files, by path relative to <home>/raw."""

    def __init__(self, home: Path | None):
        self.root = Path(home) / "raw" if home else None
        self._cache: dict[str, list[str] | None] = {}

    def lines(self, rel: str) -> list[str] | None:
        if rel not in self._cache:
            p = self.root / rel if self.root else None
            ok = p is not None and p.is_file() and self.root.resolve() in p.resolve().parents
            self._cache[rel] = p.read_text().splitlines() if ok else None
        return self._cache[rel]

    def has_quote(self, rel: str, line_no: int, quote: str) -> str | None:
        lines = self.lines(rel)
        if lines is None:
            return f"raw file {rel} not found"
        if not 1 <= line_no <= len(lines) or normalise(quote) not in normalise(lines[line_no - 1]):
            return f"quote is not in {rel} line {line_no}"
        return None


def check_memo_text(memo: str, valuation: dict, params: dict, store: FactStore | None = None,
                    extra_identifiers: tuple[str, ...] = (), extra_docs: tuple = (),
                    raw: _RawText | None = None) -> tuple[list[str], int, int]:
    """Check 3 on its own. Returns (errors, numbers checked, quotes checked)."""
    errors: list[str] = []
    numbers: list[float] = []
    strings: list[str] = []
    for doc in (valuation, params, *extra_docs):
        _leaves(doc, numbers, strings)
    numbers.sort()
    known_strings = set(strings) | set(extra_identifiers)
    known_dates = {d for s in strings for d in _DATE.findall(s)}
    raw = raw or _RawText(None)

    def near(x: float, tol: float) -> bool:
        i = bisect.bisect_left(numbers, x - tol)
        return i < len(numbers) and numbers[i] <= x + tol

    # quotes: verified against the raw filing text, then removed (their figures are the filing's own)
    quotes = 0
    for quote, rel, line_no in _QUOTE_LINE.findall(memo):
        quotes += 1
        err = raw.has_quote(rel, int(line_no), quote)
        if err:
            errors.append(f"memo quote fails verification: {err}")
    text = _QUOTE_LINE.sub(" ", memo)
    if re.search(r"^\s*>", text, re.M):
        errors.append("memo has a quote that is not in the verifiable form")

    # links: the target must be a recorded source
    for _, url in _LINK.findall(text):
        if url not in known_strings:
            errors.append(f"memo links to {url}, which is not a recorded source")
    text = _LINK.sub(lambda m: m.group(1), text)

    # identifiers in backticks
    for code in _CODE.findall(text):
        if code.startswith(("CIK", "T2/")):
            if code not in valuation.get("facts_used", {}) and code not in known_strings:
                errors.append(f"memo cites fact `{code}` that this run did not use")
            elif store is not None and store.fact_by_id(code) is None:
                errors.append(f"memo cites fact `{code}` that is not in the store")
        elif code.startswith("PX/"):
            if code != valuation["market"]["price_id"]:
                errors.append(f"memo cites price `{code}` that this valuation did not use")
        elif "." in code and code.split(".")[0] in {n.split(".")[0] for n in REQUIRED}:
            if code not in params.get("params", {}):
                errors.append(f"memo names unknown parameter `{code}`")
        elif code not in known_strings:
            errors.append(f"memo contains unrecognised identifier `{code}`")

    text = _CODE.sub(" ", text).replace(valuation["meta"]["name"], " ")
    for d in _DATE.findall(text):
        if d not in known_dates:
            errors.append(f"memo date {d} is not in the valuation")
    text = _ALLOWED_WORDS.sub(" ", _DATE.sub(" ", text))

    count = 0
    for mt in _NUMBER.finditer(text):
        count += 1
        digits = mt.group("int").replace(",", "") + (mt.group("frac") or "")
        x = float(digits) * _SCALE[mt.group("suf")] * (-1 if mt.group("sign") else 1)
        decimals = len(mt.group("frac") or ".") - 1
        if mt.group("cur") or mt.group("suf"):
            tol = 0.5 * 10 ** (-decimals) * _SCALE[mt.group("suf")] * (1 + 1e-6)  # displayed rounding
        else:
            tol = abs(x) * 1e-9 + 1e-12  # bare numbers are printed in full and must match exactly
        if not near(x, tol):
            line = memo[: memo.find(mt.group(0))].count("\n") + 1 if mt.group(0) in memo else 0
            errors.append(f"memo figure {mt.group(0)!r} (near line {line}) matches nothing in the valuation or parameters")
    return errors, count, quotes


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def check_run(run_dir: Path, store: FactStore, home: Path | None = None) -> CheckReport:
    from ..agents.verify import reverify_tier2

    run_dir = Path(run_dir)
    home = Path(home) if home else run_dir.parent.parent
    saved = json.loads((run_dir / "valuation.json").read_text())
    params_doc = json.loads((run_dir / "params.json").read_text())
    memo = (run_dir / "memo.md").read_text()
    findings = _load(run_dir / "findings.json", None)
    sources = _load(run_dir / "sources.json", [])
    raw = _RawText(home)
    ticker = saved["meta"]["ticker"]
    errors: list[str] = []

    # 1. cited facts and price against the store (and, for tier 2, against the raw filing text)
    for fid, ref in saved["facts_used"].items():
        f = store.fact_by_id(fid)
        if f is None:
            errors.append(f"fact {fid} is not in the store")
            continue
        if (f.value is None) != (ref["value"] is None) or (
                f.value is not None and not math.isclose(f.value, ref["value"], rel_tol=1e-12, abs_tol=1e-9)):
            errors.append(f"fact {fid}: valuation has {ref['value']!r}, store has {f.value!r}")
        if ref.get("tier") == 2 and ref.get("status") == "found":
            lines = raw.lines(f"{ticker}/{ref['document']}")
            err = "raw filing text not found" if lines is None else reverify_tier2(ref, lines)
            if err:
                errors.append(f"fact {fid}: {err}")
    px = store.price_by_id(saved["market"]["price_id"])
    if px is None:
        errors.append(f"price {saved['market']['price_id']} is not in the store")
    elif not math.isclose(px.close, saved["market"]["price"], rel_tol=1e-12):
        errors.append(f"price {px.price_id}: valuation has {saved['market']['price']!r}, store has {px.close!r}")

    # 2. recompute from the store and the saved parameters
    params = ParamSet.from_json(params_doc)
    if params.hash != saved["meta"]["params_hash"]:
        errors.append(f"params.json hashes to {params.hash}, valuation records {saved['meta']['params_hash']}")
    saved_v = Valuation.model_validate(saved)
    meta = saved_v.meta
    try:
        again = run_valuation(store, meta.ticker, meta.as_of, meta.price_source, params, meta.knowledge_time)
        _diff(saved, json.loads(again.model_dump_json()), "", errors)
        bear = (findings or {}).get("bear") or {}
        if bear.get("scenario"):
            overrides = {o["param"]: o["proposed_base"] for o in bear["overrides"]}
            scenario = run_with_overrides(store, saved_v, params, overrides)
            _diff(bear["scenario"], {"equity": json.loads(scenario.equity.model_dump_json()),
                                     "verdict": scenario.decision.verdict}, "/bear/scenario", errors)
    except Exception as exc:  # a run that cannot be recomputed has not been reconciled
        errors.append(f"recompute failed: {type(exc).__name__}: {exc}")

    # 3. memo text
    run_meta = json.loads((run_dir / "meta.json").read_text())
    ids = (run_meta["run_id"], run_meta.get("model_id") or "none", "raw")
    memo_errors, n, q = check_memo_text(memo, saved, params_doc, store, ids, (findings or {}, sources), raw)
    errors += memo_errors

    # 4. filing documents unchanged since the run
    for src in sources:
        if "/filings/" in src["path"]:
            p = raw.root / src["path"]
            if not p.is_file():
                errors.append(f"source {src['path']} is missing")
            elif hashlib.sha256(p.read_bytes()).hexdigest() != src["sha256"]:
                errors.append(f"source {src['path']} has changed since the run")
    return CheckReport(passed=not errors, errors=errors, facts_checked=len(saved["facts_used"]),
                       numbers_checked=n, quotes_checked=q)
