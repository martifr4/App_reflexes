"""GPU rental prices -> data/gpu_rental.csv.

Sources:
  * Silicon Data rental index pages (the indices underlying CME GPU1/GPU2).
    Each public page carries two readings that are not always equal:
      - the FAQ sentence "The current H100 rental price is $X per GPU-hour"
      - the "Related indices" widget on the *other* GPU's page ("$Y, Z% (7D)")
    We record both as separate series. Only today's value is public, so the
    daily snapshot is the only way to build a history.
  * InferenceX GPU cost assumptions (written by fetch_inferencex.py).
  * Any rows with method=manual already in gpu_rental.csv are preserved.
"""
from __future__ import annotations

import html
import re

import pandas as pd

from common import DATA, http_get, load_config, today

PAGE = "https://www.silicondata.com/products/silicon-index/{gpu}"
TICKERS = {"h100": "SDH100RT", "b200": "SDB200RT"}


def page_text(url: str) -> str:
    t = http_get(url).text
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def fetch_silicondata(cfg) -> list[dict]:
    texts = {g: page_text(PAGE.format(gpu=g)) for g in cfg["gpus"]}
    rows = []
    for g in cfg["gpus"]:
        G = g.upper()
        m = re.search(rf"current {G} rental price is \$([\d.]+) per GPU-hour", texts[g])
        if m:
            rows.append({"gpu": g, "series": "silicondata_index_faq",
                         "price_per_gpu_hour": float(m.group(1)),
                         "source_url": PAGE.format(gpu=g),
                         "notes": f"FAQ text on index page ({TICKERS.get(g)}, neocloud on-demand)"})
        # widget reading of this GPU, found on another GPU's page
        for other, t in texts.items():
            if other == g:
                continue
            m = re.search(rf"\b{G} Bloomberg ticker: (\S+) View \$([\d.]+) (-?[\d.]+)% \(7D\)", t)
            if m:
                rows.append({"gpu": g, "series": "silicondata_index_widget",
                             "price_per_gpu_hour": float(m.group(2)),
                             "source_url": PAGE.format(gpu=other),
                             "notes": f"'Related indices' widget, ticker {m.group(1)}, 7D change {m.group(3)}%"})
                break
    for r in rows:
        r.update(retrieved_date=today(), estimate=False, method="scraped")
    return rows


def main():
    cfg = load_config()
    path = DATA / "gpu_rental.csv"
    manual = pd.DataFrame()
    if path.exists():
        old = pd.read_csv(path)
        manual = old[old.method == "manual"]
    rows = fetch_silicondata(cfg)
    found = {(r["gpu"], r["series"]) for r in rows}
    for g in cfg["gpus"]:
        if (g, "silicondata_index_faq") not in found:
            print(f"WARNING: Silicon Data FAQ value not found for {g} (page layout changed?)")
    costs_path = DATA / "inferencex_gpu_costs.csv"
    ix = pd.read_csv(costs_path).assign(method="fetched") if costs_path.exists() else pd.DataFrame()
    df = pd.concat([pd.DataFrame(rows), ix, manual], ignore_index=True)
    cols = ["gpu", "series", "price_per_gpu_hour", "method", "source_url",
            "retrieved_date", "estimate", "notes"]
    df[cols].to_csv(path, index=False)
    print(f"gpu_rental.csv: {len(df)} rows")
    print(df[["gpu", "series", "price_per_gpu_hour"]].to_string(index=False))


if __name__ == "__main__":
    main()
