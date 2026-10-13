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
    closed_path, be_path = DATA / "api_prices_price_only.csv", OUT / "breakeven_throughput.csv"
    closed = pd.read_csv(closed_path) if closed_path.exists() else pd.DataFrame()
    be = pd.read_csv(be_path) if be_path.exists() else pd.DataFrame()
    elec_path, gp_path, ch_path = DATA / "electricity_prices.csv", DATA / "gpu_power.csv", OUT / "power_chain.csv"
    elec = pd.read_csv(elec_path) if elec_path.exists() else pd.DataFrame()
    gpw = pd.read_csv(gp_path) if gp_path.exists() else pd.DataFrame()
    chain = pd.read_csv(ch_path) if ch_path.exists() else pd.DataFrame()
    fsrc_path, fe_path, vs_path = DATA / "rental_firm_sources.csv", OUT / "firm_economics.csv", OUT / "value_split.csv"
    fsrc = pd.read_csv(fsrc_path) if fsrc_path.exists() else pd.DataFrame()
    fe = pd.read_csv(fe_path) if fe_path.exists() else pd.DataFrame()
    vs = pd.read_csv(vs_path) if vs_path.exists() else pd.DataFrame()
    rk_path = OUT / "profit_ranking.csv"
    rk = pd.read_csv(rk_path) if rk_path.exists() else pd.DataFrame()
    if "avg_power_w" not in tput:
        tput["avg_power_w"] = None

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
            "input_tput_per_gpu": "tin", "output_tput_per_gpu": "tout", "avg_power_w": "pw",
            "median_intvty": "intv", "median_ttft": "ttft", "bench_date": "date",
            "source_url": "url"}),
        "rental": records(rental, {
            "gpu": "gpu", "series": "series", "price_per_gpu_hour": "price", "method": "method",
            "source_url": "url", "retrieved_date": "date", "estimate": "estimate",
            "notes": "notes"}),
        "closed": records(closed, {
            "model_key": "m", "openrouter_id": "id", "lab": "lab", "tier": "tier",
            "weights": "weights", "reason": "reason",
            "list_input_price_per_Mtok": "linp", "list_output_price_per_Mtok": "lout",
            "list_cache_read_price_per_Mtok": "lcache", "provider": "provider",
            "endpoint_tag": "tag", "input_price_per_Mtok": "inp",
            "output_price_per_Mtok": "out", "cache_read_price_per_Mtok": "cache",
            "context_length": "ctx", "model_created": "created", "source_url": "url",
            "list_source_url": "list_url", "retrieved_date": "date"}) if len(closed) else [],
        "python_breakeven": records(be, {
            "model": "m", "gpu": "gpu", "breakeven_tput_per_gpu": "be"}) if len(be) else [],
        "electricity": records(elec, {
            "region": "region", "label": "label", "country": "country", "sector": "sector",
            "price_usd_per_kwh": "price", "price_local": "local", "currency": "cur", "period": "period",
            "fx_usd_per_eur": "fx", "source_url": "url", "retrieved_date": "date", "notes": "notes"}) if len(elec) else [],
        "gpu_power": records(gpw, {
            "gpu": "gpu", "tdp_w": "tdp", "allin_kw": "kw", "owner_tco_per_hour": "tco",
            "retail_per_hour": "retail", "source_url": "url", "retrieved_date": "date",
            "notes": "notes"}) if len(gpw) else [],
        "python_power": records(chain, {
            "model": "m", "gpu": "gpu", "precision": "prec", "power_cost": "power",
            "revenue_per_kwh": "rpk", "measured_gpu_w": "mw"}) if len(chain) else [],
        "firm_sources": records(fsrc, {
            "item": "item", "gpu": "gpu", "value": "value", "unit": "unit", "low": "low", "high": "high",
            "used_in_model": "used", "source_url": "url", "retrieved_date": "date", "estimate": "estimate",
            "notes": "notes"}) if len(fsrc) else [],
        "python_firm": records(fe[fe.base], {
            "gpu": "gpu", "full_cost": "full", "profit": "profit", "ebitda_margin": "ebitda"}) if len(fe) else [],
        "python_split": records(vs, {
            "model": "m", "gpu": "gpu", "precision": "prec", "landlord_profit": "landlord",
            "integrated_profit": "integrated"}) if len(vs) else [],
        "python_ranking": records(rk, {
            "model": "m", "gpu": "gpu", "revenue": "revenue", "profit": "profit"}) if len(rk) else [],
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
