"""Electricity prices and per-GPU power -> data/electricity_prices.csv, data/gpu_power.csv.

Sources (all public, no key):
  * US: EIA Electric Power Monthly, table 5.6.A (average price by state and sector,
    latest month, cents/kWh).
  * Europe: Eurostat nrg_pc_205 (non-household prices, bi-annual, EUR/kWh, excl. VAT
    and recoverable taxes) for the configured consumption band.
  * EUR->USD: ECB daily reference rate.
  * GPU power: InferenceX's open-source GPU constants (TDP and SemiAnalysis "all-in"
    kW per GPU, which includes the GPU's share of host CPU, RAM and NICs).
"""
from __future__ import annotations

import html
import re

import pandas as pd

from common import DATA, http_get, load_config, today

EIA_URL = "https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_a"
EUROSTAT_URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_205"
                "?format=JSON&lang=en&nrg_cons={band}&tax=X_VAT&currency=EUR&unit=KWH&lastTimePeriod=2")
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=1&format=csvdata"
GPU_KEYS_URL = "https://raw.githubusercontent.com/SemiAnalysisAI/InferenceX-app/main/packages/constants/src/gpu-keys.ts"
GPU_KEYS_PAGE = "https://github.com/SemiAnalysisAI/InferenceX-app/blob/main/packages/constants/src/gpu-keys.ts"
SECTORS = ["residential", "commercial", "industrial", "transportation", "all"]


def eia_prices() -> tuple[dict, str]:
    """{(state, sector): cents/kWh for the latest month}, month label."""
    t = http_get(EIA_URL).text
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", t)))
    month = re.search(r"by State, (\w+ \d{4}) and", text).group(1)
    # Walk the table cells: a row is a name followed by 10 values
    # (latest month and same month last year, for 5 sectors; '--' when missing).
    cells = [c.strip() for c in text.split("|") if c.strip()]
    num = re.compile(r"^(?:\d+\.\d+|--)$")
    out = {}
    for i, c in enumerate(cells[:-10]):
        if num.match(c) or not re.match(r"^[A-Z][A-Za-z. ]+$", c):
            continue
        vals = cells[i + 1:i + 11]
        if all(num.match(v) for v in vals):
            for j, sector in enumerate(SECTORS):
                v = vals[2 * j]  # latest month
                if v != "--":
                    out[(c, sector)] = float(v)
    return out, month


def eurostat_prices(band: str) -> tuple[dict, str]:
    """{geo: EUR/kWh for the latest period with data}, period label."""
    d = http_get(EUROSTAT_URL.format(band=band)).json()
    geo_idx = d["dimension"]["geo"]["category"]["index"]
    times = sorted(d["dimension"]["time"]["category"]["index"].items(), key=lambda kv: kv[1])
    n_time = len(times)
    out, period = {}, {}
    for geo, gi in geo_idx.items():
        for label, ti in reversed(times):  # newest first
            v = d["value"].get(str(gi * n_time + ti))
            if v is not None:
                out[geo], period[geo] = v, label
                break
    return out, period


def ecb_usd_per_eur() -> tuple[float, str]:
    lines = http_get(ECB_URL).text.strip().splitlines()
    row = dict(zip(lines[0].split(","), lines[1].split(",")))
    return float(row["OBS_VALUE"]), row["TIME_PERIOD"]


def gpu_power(gpus) -> pd.DataFrame:
    src = http_get(GPU_KEYS_URL).text
    rows = []
    for g in gpus:
        m = re.search(rf"\b{g}: \{{[^}}]*?tdp: (\d+),\s*power: ([\d.]+),\s*costh: ([\d.]+),\s*costr: ([\d.]+)", src)
        if not m:
            print(f"WARNING: no power constants for {g}")
            continue
        rows.append({"gpu": g, "tdp_w": int(m.group(1)), "allin_kw": float(m.group(2)),
                     "owner_tco_per_hour": float(m.group(3)), "retail_per_hour": float(m.group(4)),
                     "source_url": GPU_KEYS_PAGE, "retrieved_date": today(), "estimate": True,
                     "notes": "SemiAnalysis AI Cloud TCO model values as published in InferenceX; "
                              "allin_kw = GPU + per-GPU share of host/NICs at full load (IT power, before PUE)"})
    return pd.DataFrame(rows)


def main():
    cfg = load_config()
    pw = cfg["power"]
    rows = []
    regions = pw["regions"]
    if any(r["source"] == "eia" for r in regions):
        eia, month = eia_prices()
        for r in (r for r in regions if r["source"] == "eia"):
            v = eia.get((r["state"], r["sector"]))
            if v is None:
                print(f"WARNING: EIA value missing for {r['state']} / {r['sector']}")
                continue
            rows.append({"region": r["key"], "label": r["label"], "country": "US", "sector": r["sector"],
                         "price_usd_per_kwh": round(v / 100, 5), "price_local": v / 100, "currency": "USD",
                         "period": month, "fx_usd_per_eur": None, "source_url": EIA_URL,
                         "notes": f"EIA table 5.6.A, {r['state']}, {r['sector']} sector, average retail price"})
    if any(r["source"] == "eurostat" for r in regions):
        es, period = eurostat_prices(pw["eurostat_band"])
        fx, fx_date = ecb_usd_per_eur()
        for r in (r for r in regions if r["source"] == "eurostat"):
            v = es.get(r["geo"])
            if v is None:
                print(f"WARNING: Eurostat value missing for {r['geo']}")
                continue
            rows.append({"region": r["key"], "label": r["label"], "country": r["geo"], "sector": "non-household",
                         "price_usd_per_kwh": round(v * fx, 5), "price_local": v, "currency": "EUR",
                         "period": period[r["geo"]], "fx_usd_per_eur": fx,
                         "source_url": EUROSTAT_URL.format(band=pw["eurostat_band"]),
                         "notes": f"Eurostat nrg_pc_205, band {pw['eurostat_band']} kWh/yr, excl. VAT; "
                                  f"EUR->USD at ECB rate {fx} ({fx_date})"})
    df = pd.DataFrame(rows).assign(retrieved_date=today(), estimate=False)
    df.to_csv(DATA / "electricity_prices.csv", index=False)
    print(f"electricity_prices.csv: {len(df)} regions")
    print(df[["region", "price_usd_per_kwh", "period"]].to_string(index=False))
    gp = gpu_power(cfg["gpus"])
    gp.to_csv(DATA / "gpu_power.csv", index=False)
    print(f"gpu_power.csv: {len(gp)} GPUs")


if __name__ == "__main__":
    main()
