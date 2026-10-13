# Token Spread v0

Estimates the **token spread**: the gap between what a GPU-hour earns serving open-weight LLM
inference at market API prices and what that GPU-hour costs to rent.

The question: does the token-implied value of a GPU-hour tell us anything that GPU rental
indices don't — e.g. which chips or models are over- or under-priced, and how much margin
inference providers have?

Latest results: [`report.md`](report.md).

## Method

For each (model, GPU, precision, provider):

```
blended_price_per_Mtok       = (r · input_price + output_price) / (r + 1)     r = input:output token ratio
tokens_per_gpu_hour          = throughput_tok_s_per_gpu · 3600 · utilization
implied_revenue_per_gpu_hour = tokens_per_gpu_hour / 1e6 · blended_price_per_Mtok
token_spread                 = implied_revenue_per_gpu_hour − gpu_rental_price_per_hour
spread_ratio                 = implied_revenue_per_gpu_hour / gpu_rental_price_per_hour
breakeven_utilization        = rental / (revenue at 100% utilization)
```

`throughput_tok_s_per_gpu` is **total** (input + output) tokens per second per GPU, measured
with the same input:output mix as the price blend.

**Choosing the throughput point.** Benchmarks sweep concurrency. Higher concurrency means
more tokens per GPU but slower streams per user. We take the highest-throughput point whose
median interactivity is at least `interactivity_floor_tok_s_per_user` (default 30 tok/s, a
usable API stream). The point with no latency floor is reported as an upper bound.

**Input:output ratios.** InferenceX measures 1k/1k (1:1), 8k/1k (8:1) and 1k/8k (1:8). Other
ratios are interpolated linearly in log(ratio) and held flat outside the measured range. Those
rows have `estimate=True`.

All assumptions live in [`assumptions.yaml`](assumptions.yaml).

## Data sources

| File | Source | Fetch |
|---|---|---|
| `data/api_prices.csv` | [OpenRouter](https://openrouter.ai) `GET /api/v1/models/{id}/endpoints`: per-provider list prices and quantization | `fetch/fetch_openrouter.py` |
| `data/throughput.csv` | [SemiAnalysis InferenceX](https://inferencex.semianalysis.com) `GET /api/v1/benchmarks?model=…`: per-GPU throughput across framework, precision, ISL/OSL and concurrency. Each row links its GitHub Actions run (`source_url`). Only the latest run date per configuration is kept. | `fetch/fetch_inferencex.py` |
| `data/gpu_rental.csv` | [Silicon Data](https://www.silicondata.com/products/silicon-index/h100) H100/B200 rental index pages (SDH100RT / SDB200RT, the indices underlying CME GPU1/GPU2 futures). Two readings per page (FAQ text and widget) are both recorded. Also includes InferenceX's retail and owner-TCO $/GPU-hr assumptions (`estimate=True`). Rows with `method=manual` are preserved across fetches, so you can add your own. | `fetch/fetch_silicondata.py` |

Every data row has `source_url`, `retrieved_date`, `estimate` and `notes`.

## Layout

```
assumptions.yaml        every modelling assumption
fetch/                  fetchers (run_all.py runs all; a failed source keeps its previous CSV)
data/                   current raw inputs
compute.py              join + spread -> outputs/*.csv, and a snapshot
report.py               report.md + charts/*.png
outputs/                spread_summary, sensitivity, provider_spread, operating_points
snapshots/<date>/       copies of inputs/outputs that changed since the last stored copy
snapshots/timeseries.csv  one row per base case per run date
```

## Re-running

```bash
cd token_spread
pip install -r requirements.txt
python fetch/run_all.py   # pull fresh data
python compute.py         # spread + snapshot
python report.py          # report.md + charts
```

To change an assumption, edit `assumptions.yaml` and re-run `compute.py` and `report.py`
(no fetch needed).

## Daily time series

`.github/workflows/token-spread-daily.yml` runs fetch + compute every day at 06:17 UTC and
commits the snapshot. `report.md` is regenerated on Mondays and on manual runs.

Why daily: Silicon Data's free page and OpenRouter's API expose only **current** values, so the
daily snapshot is the only way to get their history. InferenceX keeps its own history and
changes in steps every few weeks. Unchanged files are not re-copied, so `snapshots/` grows
slowly.

GitHub runs scheduled workflows only from the default branch, so the job starts once this
is merged to `main`. It can also be started manually from the Actions tab.

## Known limitations

See the "Data gaps and caveats" section of `report.md`. In short: benchmark throughput ≠
production throughput, 3:1 and 10:1 ratios are interpolated, configurations are not matched
across GPUs, prices are list prices, and rental is neocloud on-demand.
