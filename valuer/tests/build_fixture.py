"""Slim a raw EDGAR companyfacts file down to the concepts the mapping uses.

    python tests/build_fixture.py data/raw/edgar/companyfacts-59527.<date>.json \
        data/raw/edgar/submissions-59527.<date>.json LECO
"""
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent


def concepts(node, out):
    if isinstance(node, str):
        out.add(node)
    elif isinstance(node, list):
        for x in node:
            concepts(x, out)
    elif isinstance(node, dict):
        for k, x in node.items():
            if k not in ("key", "label", "class", "haircut", "gap_if_present"):
                concepts(x, out)


def main(facts_path, subs_path, ticker):
    keep = set()
    concepts(yaml.safe_load((HERE.parent / "src/valuer/mapping/line_items.yaml").read_text()), keep)
    doc = json.loads(Path(facts_path).read_text())
    doc["facts"] = {tax: {c: b for c, b in body.items() if c in keep} for tax, body in doc["facts"].items()}
    (HERE / "fixtures" / f"{ticker}_companyfacts.json").write_text(json.dumps(doc, separators=(",", ":")))
    sub = json.loads(Path(subs_path).read_text())
    recent = sub["filings"]["recent"]
    idx = [i for i, f in enumerate(recent["form"]) if f in ("10-K", "10-Q")][:8]
    slim = {k: sub.get(k) for k in ("cik", "name", "sic", "sicDescription", "fiscalYearEnd", "tickers")}
    slim["filings"] = {"recent": {k: [v[i] for i in idx] for k, v in recent.items()}}
    (HERE / "fixtures" / f"{ticker}_submissions.json").write_text(json.dumps(slim, separators=(",", ":")))


if __name__ == "__main__":
    main(*sys.argv[1:4])
