"""Reconcile a saved run against the fact store. Any mismatch fails the run.

Three checks:
1. Every fact and price the valuation cites still exists in the store with the same value.
2. Recomputing the valuation from the store and the saved parameters reproduces the saved one.
3. Every number, date and backticked identifier in the memo traces to the valuation, the
   parameters or the store. A number that matches nothing is an error, whoever wrote it.
"""
from __future__ import annotations

import bisect
import json
import math
import re
from pathlib import Path

from pydantic import BaseModel

from ..params import REQUIRED, ParamSet
from ..store.store import FactStore
from ..valuation.engine import run_valuation
from ..valuation.types import Valuation

_CODE = re.compile(r"`([^`]*)`")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
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


def check_memo_text(memo: str, valuation: dict, params: dict, store: FactStore | None = None,
                    extra_identifiers: tuple[str, ...] = ()) -> tuple[list[str], int]:
    """Check 3 on its own. Returns (errors, count of numbers checked)."""
    errors: list[str] = []
    numbers: list[float] = []
    strings: list[str] = []
    _leaves(valuation, numbers, strings)
    _leaves(params, numbers, strings)
    numbers.sort()
    known_strings = set(strings) | set(extra_identifiers)
    known_dates = {d for s in strings for d in _DATE.findall(s)}

    def near(x: float, tol: float) -> bool:
        i = bisect.bisect_left(numbers, x - tol)
        return i < len(numbers) and numbers[i] <= x + tol

    # identifiers in backticks
    for code in _CODE.findall(memo):
        if code.startswith("CIK"):
            if code not in valuation.get("facts_used", {}):
                errors.append(f"memo cites fact `{code}` that this valuation did not use")
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

    text = _CODE.sub(" ", memo).replace(valuation["meta"]["name"], " ")
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
    return errors, count


def check_run(run_dir: Path, store: FactStore) -> CheckReport:
    run_dir = Path(run_dir)
    saved = json.loads((run_dir / "valuation.json").read_text())
    params_doc = json.loads((run_dir / "params.json").read_text())
    memo = (run_dir / "memo.md").read_text()
    errors: list[str] = []

    # 1. cited facts and price against the store
    for fid, ref in saved["facts_used"].items():
        f = store.fact_by_id(fid)
        if f is None:
            errors.append(f"fact {fid} is not in the store")
        elif not math.isclose(f.value, ref["value"], rel_tol=1e-12, abs_tol=1e-9):
            errors.append(f"fact {fid}: valuation has {ref['value']!r}, store has {f.value!r}")
    px = store.price_by_id(saved["market"]["price_id"])
    if px is None:
        errors.append(f"price {saved['market']['price_id']} is not in the store")
    elif not math.isclose(px.close, saved["market"]["price"], rel_tol=1e-12):
        errors.append(f"price {px.price_id}: valuation has {saved['market']['price']!r}, store has {px.close!r}")

    # 2. recompute from the store and the saved parameters
    params = ParamSet.from_json(params_doc)
    if params.hash != saved["meta"]["params_hash"]:
        errors.append(f"params.json hashes to {params.hash}, valuation records {saved['meta']['params_hash']}")
    meta = Valuation.model_validate(saved).meta
    try:
        again = run_valuation(store, meta.ticker, meta.as_of, meta.price_source, params)
        _diff(saved, json.loads(again.model_dump_json()), "", errors)
    except Exception as exc:  # a run that cannot be recomputed has not been reconciled
        errors.append(f"recompute failed: {type(exc).__name__}: {exc}")

    # 3. memo text
    run_meta = json.loads((run_dir / "meta.json").read_text())
    ids = (run_meta["run_id"], run_meta.get("model_id") or "none")
    memo_errors, n = check_memo_text(memo, saved, params_doc, store, ids)
    errors += memo_errors
    return CheckReport(passed=not errors, errors=errors, facts_checked=len(saved["facts_used"]), numbers_checked=n)
