"""Bitcoin network state -> data/bitcoin_network.csv (one row, refreshed daily).

Source: mempool.space public API (no key):
  * /api/v1/prices                       BTC/USD
  * /api/v1/mining/hashrate/1w           current difficulty and network hashrate
  * /api/v1/mining/reward-stats/<n>      total reward and fees over the last n blocks
The block subsidy follows the halving schedule: 50 BTC / 2^(height // 210,000).
Per-device hash rates are not fetched: they live in data/mining_hardware.csv (sourced by hand).
"""
from __future__ import annotations

import pandas as pd

from common import DATA, http_get, load_config, today

API = "https://mempool.space/api/v1"
PAGE = "https://mempool.space/mining"


def main():
    cfg = load_config()["bitcoin"]
    n = cfg["fee_window_blocks"]
    price = http_get(f"{API}/prices").json()["USD"]
    hr = http_get(f"{API}/mining/hashrate/1w").json()
    rs = http_get(f"{API}/mining/reward-stats/{n}").json()
    sats = 1e8
    fees = int(rs["totalFee"]) / sats
    blocks = rs["endBlock"] - rs["startBlock"] + 1
    row = {
        "btc_price_usd": float(price),
        "difficulty": float(hr["currentDifficulty"]),
        "network_hashrate_ehs": float(hr["currentHashrate"]) / 1e18,
        "block_subsidy_btc": 50 / 2 ** (rs["endBlock"] // 210_000),
        "fees_per_block_btc": fees / blocks,
        "fee_window_blocks": blocks,
        "tip_height": rs["endBlock"],
        "source_url": PAGE,
        "retrieved_date": today(),
        "estimate": False,
        "notes": f"mempool.space API: price, current difficulty, average reward over blocks {rs['startBlock']}-{rs['endBlock']}",
    }
    pd.DataFrame([row]).to_csv(DATA / "bitcoin_network.csv", index=False)
    print(f"bitcoin_network.csv: ${price:,.0f}, difficulty {row['difficulty']:.4g}, "
          f"{row['block_subsidy_btc']} BTC subsidy + {row['fees_per_block_btc']:.4f} fees/block")


if __name__ == "__main__":
    main()
