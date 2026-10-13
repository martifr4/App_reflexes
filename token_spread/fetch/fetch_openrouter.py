"""Per-provider API prices for each model from OpenRouter -> data/api_prices.csv.

Endpoint: GET https://openrouter.ai/api/v1/models/{id}/endpoints (public, no key).
Prices in the API are USD per token; we store USD per million tokens.
"""
from __future__ import annotations

import pandas as pd

from common import DATA, http_get, load_config, today

URL = "https://openrouter.ai/api/v1/models/{id}/endpoints"


def per_mtok(v) -> float | None:
    return None if v in (None, "") else round(float(v) * 1e6, 6)


def fetch() -> pd.DataFrame:
    cfg = load_config()
    rows = []
    for m in cfg["models"]:
        url = URL.format(id=m["openrouter_id"])
        data = http_get(url).json()["data"]
        for e in data["endpoints"]:
            p = e["pricing"]
            rows.append({
                "model_key": m["key"],
                "openrouter_id": m["openrouter_id"],
                "provider": e["provider_name"],
                "endpoint_tag": e.get("tag"),
                "quantization": e.get("quantization") or "unknown",
                "input_price_per_Mtok": per_mtok(p.get("prompt")),
                "output_price_per_Mtok": per_mtok(p.get("completion")),
                "cache_read_price_per_Mtok": per_mtok(p.get("input_cache_read")),
                "discount": p.get("discount", 0),
                "context_length": e.get("context_length"),
                "uptime_last_1d": e.get("uptime_last_1d"),
                "source_url": url,
                "retrieved_date": today(),
                "estimate": False,
                "notes": "OpenRouter list price; excludes volume/batch deals",
            })
    return pd.DataFrame(rows)


def main():
    df = fetch()
    df.to_csv(DATA / "api_prices.csv", index=False)
    print(f"api_prices.csv: {len(df)} provider endpoints for {df.model_key.nunique()} models")


if __name__ == "__main__":
    main()
