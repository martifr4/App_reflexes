"""Per-GPU throughput from SemiAnalysis InferenceX -> data/throughput.csv.

Endpoint: GET https://inferencex.semianalysis.com/api/v1/benchmarks?model=<name>
Each row is one benchmark point: (hardware, framework, precision, ISL/OSL,
concurrency, parallelism) with per-GPU throughput and latency metrics, plus a
GitHub Actions run_url that produced it.

We keep fixed-sequence rows (not agentic traces) for the configured GPUs (and, when
`inferencex_key` is set, only that model variant) and,
for each configuration, only the most recent run date. Older runs remain
available from InferenceX itself.

Also writes the InferenceX GPU cost assumptions (owner TCO / retail $/GPU-hr)
to data/inferencex_gpu_costs.csv, used as a rental cross-check.
"""
from __future__ import annotations

import pandas as pd

from common import DATA, http_get, load_config, today

BASE = "https://inferencex.semianalysis.com/api/v1"
CONFIG_KEYS = ["hardware", "framework", "precision", "spec_method", "disagg",
               "is_multinode", "isl", "osl"]
METRICS = ["tput_per_gpu", "input_tput_per_gpu", "output_tput_per_gpu",
           "median_intvty", "median_ttft", "median_tpot",
           "avg_power_w", "joules_per_total_token"]  # measured GPU power: newer runs only


def fetch_throughput(cfg) -> pd.DataFrame:
    out = []
    for m in cfg["models"]:
        url = f"{BASE}/benchmarks?model={m['inferencex_model']}"
        rows = http_get(url).json()
        for r in rows:
            if r["hardware"] not in cfg["gpus"] or r.get("isl") is None:
                continue
            if m.get("inferencex_key") and r["model"] != m["inferencex_key"]:
                continue
            met = r["metrics"]
            out.append({
                "model_key": m["key"],
                "inferencex_model": m["inferencex_model"],
                **{k: r[k] for k in CONFIG_KEYS},
                "conc": r["conc"],
                "decode_tp": r.get("decode_tp"),
                "decode_ep": r.get("decode_ep"),
                "num_gpus": (r.get("num_prefill_gpu") or 0) + (r.get("num_decode_gpu") or 0)
                if r.get("disagg") else r.get("decode_tp"),
                "image": r.get("image"),
                **{k: met.get(k) for k in METRICS},
                "bench_date": r["date"],
                "source_url": r.get("run_url"),
                "api_url": url,
                "retrieved_date": today(),
                "estimate": False,
                "notes": "InferenceX random-data benchmark; per-GPU throughput incl. input+output tokens",
            })
    df = pd.DataFrame(out)
    # keep the latest run date for each configuration
    latest = df.groupby(["model_key"] + CONFIG_KEYS)["bench_date"].transform("max")
    return df[df.bench_date == latest].reset_index(drop=True)


def fetch_gpu_costs(cfg) -> pd.DataFrame:
    url = f"{BASE}/views/options"
    hw = http_get(url).json()["hardware"]
    rows = []
    for h in hw:
        if h["key"] not in cfg["gpus"]:
            continue
        for k, series, note in [
            ("r", "inferencex_retail", "InferenceX 'retail tier' $/GPU-hr assumption (SemiAnalysis TCO model)"),
            ("h", "inferencex_owner_tco", "InferenceX 'owning at hyperscaler volume' $/GPU-hr (all-in TCO, not a rental price)"),
        ]:
            rows.append({"gpu": h["key"], "series": series,
                         "price_per_gpu_hour": h["costPerHour"][k],
                         "source_url": url, "retrieved_date": today(),
                         "estimate": True, "notes": note + "; modelled, not a market quote"})
    return pd.DataFrame(rows)


def main():
    cfg = load_config()
    tp = fetch_throughput(cfg)
    tp.to_csv(DATA / "throughput.csv", index=False)
    print(f"throughput.csv: {len(tp)} benchmark points "
          f"({tp.groupby(['model_key', 'hardware']).ngroups} model×GPU pairs)")
    costs = fetch_gpu_costs(cfg)
    costs.to_csv(DATA / "inferencex_gpu_costs.csv", index=False)
    print(f"inferencex_gpu_costs.csv: {len(costs)} rows")


if __name__ == "__main__":
    main()
