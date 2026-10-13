"""API prices from OpenRouter.

-> data/api_prices.csv         open-weight models, one row per provider endpoint
-> data/api_prices_closed.csv  closed models (Claude, GPT, Grok), one row per endpoint,
                               plus the model-level list price on every row

Endpoints: GET https://openrouter.ai/api/v1/models/{id}/endpoints and
GET https://openrouter.ai/api/v1/models (public, no key).
Prices in the API are USD per token; we store USD per million tokens.
"""
from __future__ import annotations

import pandas as pd

from common import DATA, http_get, load_config, today

URL = "https://openrouter.ai/api/v1/models/{id}/endpoints"
LIST_URL = "https://openrouter.ai/api/v1/models"


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


def fetch_closed() -> pd.DataFrame:
    cfg = load_config()
    listing = {m["id"]: m for m in http_get(LIST_URL).json()["data"]}
    rows = []
    for m in cfg.get("closed_models", []):
        lm = listing.get(m["openrouter_id"])
        if lm is None:
            print(f"WARNING: {m['openrouter_id']} not listed on OpenRouter; skipped")
            continue
        url = URL.format(id=m["openrouter_id"])
        for e in http_get(url).json()["data"]["endpoints"]:
            p = e["pricing"]
            rows.append({
                "model_key": m["key"],
                "openrouter_id": m["openrouter_id"],
                "lab": m["lab"],
                "tier": m["tier"],
                "list_input_price_per_Mtok": per_mtok(lm["pricing"].get("prompt")),
                "list_output_price_per_Mtok": per_mtok(lm["pricing"].get("completion")),
                "list_cache_read_price_per_Mtok": per_mtok(lm["pricing"].get("input_cache_read")),
                "provider": e["provider_name"],
                "endpoint_tag": e.get("tag"),
                "input_price_per_Mtok": per_mtok(p.get("prompt")),
                "output_price_per_Mtok": per_mtok(p.get("completion")),
                "cache_read_price_per_Mtok": per_mtok(p.get("input_cache_read")),
                "context_length": e.get("context_length"),
                "model_created": pd.Timestamp(lm["created"], unit="s").date().isoformat(),
                "source_url": url,
                "list_source_url": LIST_URL,
                "retrieved_date": today(),
                "estimate": False,
                "notes": "Closed model: list price = OpenRouter model-level price (lab's standard tier); "
                         "endpoint rows include regional/priority/flex tiers. Tier label is a price grouping, not a disclosed size.",
            })
    return pd.DataFrame(rows)


def main():
    df = fetch()
    df.to_csv(DATA / "api_prices.csv", index=False)
    print(f"api_prices.csv: {len(df)} provider endpoints for {df.model_key.nunique()} models")
    closed = fetch_closed()
    closed.to_csv(DATA / "api_prices_closed.csv", index=False)
    print(f"api_prices_closed.csv: {len(closed)} endpoints for {closed.model_key.nunique()} closed models")


if __name__ == "__main__":
    main()
