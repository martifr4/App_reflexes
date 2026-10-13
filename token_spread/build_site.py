"""Build the static website from the latest data and outputs.

Writes:
  site/index.html     standalone page (GitHub Pages or open locally)
  site/artifact.html  same content without the document skeleton (for hosts that add one)

The page embeds every input row (prices, benchmarks, rental) plus the assumptions,
so the dashboard recomputes the spread in the browser with the same rules as compute.py.
Run after compute.py:  python build_site.py
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
DATA, OUT, SNAP, SITE = ROOT / "data", ROOT / "outputs", ROOT / "snapshots", ROOT / "site"
REPO = "https://github.com/martifr4/App_reflexes"


def branch() -> str:
    if os.environ.get("GITHUB_REF_NAME"):
        return os.environ["GITHUB_REF_NAME"]
    try:
        return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                                       text=True).strip()
    except Exception:
        return "main"


def records(df: pd.DataFrame, cols: dict[str, str]) -> list[dict]:
    """Rename columns to short keys; NaN -> None."""
    d = df[list(cols)].rename(columns=cols)
    return json.loads(d.to_json(orient="records"))


def build() -> dict:
    cfg = yaml.safe_load(open(ROOT / "assumptions.yaml"))
    prices = pd.read_csv(DATA / "api_prices.csv")
    tput = pd.read_csv(DATA / "throughput.csv")
    rental = pd.read_csv(DATA / "gpu_rental.csv")
    summary = pd.read_csv(OUT / "spread_summary.csv")
    ts_path = SNAP / "timeseries.csv"
    ts = pd.read_csv(ts_path) if ts_path.exists() else pd.DataFrame()

    b = branch()
    return {
        "meta": {
            "data_date": str(prices.retrieved_date.max()),
            "prices_retrieved": str(prices.retrieved_date.max()),
            "rental_retrieved": str(rental.retrieved_date.max()),
            "throughput_retrieved": str(tput.retrieved_date.max()),
            "newest_benchmark": str(tput.bench_date.max()),
            "repo": REPO,
            "branch": b,
            "tree_url": f"{REPO}/tree/{b}/token_spread",
            "blob_url": f"{REPO}/blob/{b}/token_spread",
        },
        "config": cfg,
        "prices": records(prices, {
            "model_key": "m", "provider": "provider", "endpoint_tag": "tag",
            "quantization": "q", "input_price_per_Mtok": "inp", "output_price_per_Mtok": "out",
            "cache_read_price_per_Mtok": "cache", "context_length": "ctx",
            "uptime_last_1d": "uptime", "source_url": "url", "retrieved_date": "date"}),
        "tput": records(tput, {
            "model_key": "m", "hardware": "gpu", "framework": "fw", "precision": "prec",
            "spec_method": "spec", "disagg": "disagg", "is_multinode": "multi", "isl": "isl",
            "osl": "osl", "conc": "conc", "num_gpus": "ngpu", "decode_tp": "tp",
            "decode_ep": "ep", "image": "image", "tput_per_gpu": "tput",
            "input_tput_per_gpu": "tin", "output_tput_per_gpu": "tout",
            "median_intvty": "intv", "median_ttft": "ttft", "bench_date": "date",
            "source_url": "url"}),
        "rental": records(rental, {
            "gpu": "gpu", "series": "series", "price_per_gpu_hour": "price", "method": "method",
            "source_url": "url", "retrieved_date": "date", "estimate": "estimate",
            "notes": "notes"}),
        "timeseries": json.loads(ts.to_json(orient="records")) if len(ts) else [],
        "python_summary": records(summary, {
            "model": "m", "gpu": "gpu", "precision": "prec", "case": "case",
            "revenue": "revenue", "spread_ratio": "ratio"}),
    }


def main():
    data = build()
    blob = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    body = (SITE / "template.html").read_text().replace("__TOKEN_SPREAD_DATA__", blob)
    (SITE / "artifact.html").write_text(body)
    page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<style>html{color-scheme:light}body{margin:0;font:14px system-ui,sans-serif}'
            'img{max-width:100%}[hidden]{display:none!important}</style>\n'
            '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    (SITE / "index.html").write_text(page)
    print(f"site/index.html: {len(page) / 1024:.0f} KB (data as of {data['meta']['data_date']})")


if __name__ == "__main__":
    main()
