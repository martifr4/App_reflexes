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

## Closed models (Claude, GPT, Grok)

Closed models publish prices but not hardware or throughput, so no spread is computed for them.
Instead `compute.py` writes:

- `outputs/breakeven_throughput.csv`: the tokens/s per GPU each model needs for its price to
  cover the GPU's rent, `rent ÷ (3600 × utilization × blended price / 1e6)`. Closed models get
  only this threshold. Open-weight models also get their measured throughput, and
  measured ÷ needed = spread ratio.
- `outputs/price_comparison.csv`: blended prices of every model, open and closed.

Closed-model prices use OpenRouter's model-level list price (the lab's standard tier). Endpoint
tiers (regional, priority, flex) are kept as a range in `data/api_prices_closed.csv`. The model
list is `closed_models` in `assumptions.yaml`.

## Data sources

| File | Source | Fetch |
|---|---|---|
| `data/api_prices.csv` | [OpenRouter](https://openrouter.ai) `GET /api/v1/models/{id}/endpoints`: per-provider list prices and quantization | `fetch/fetch_openrouter.py` |
| `data/api_prices_closed.csv` | OpenRouter `GET /api/v1/models` (list price) and `/models/{id}/endpoints` for each closed model | `fetch/fetch_openrouter.py` |
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
build_site.py, site/    the website (template.html -> index.html)
```

## Re-running

```bash
cd token_spread
pip install -r requirements.txt
python fetch/run_all.py   # pull fresh data
python compute.py         # spread + snapshot
python report.py          # report.md + charts
python build_site.py      # site/index.html
```

To change an assumption, edit `assumptions.yaml` and re-run `compute.py` and `report.py`
(no fetch needed).

## Website

`python build_site.py` writes `site/index.html`: a single self-contained page with the
findings, an explainer of every concept, an interactive dashboard and the full raw data.
It embeds every input row and recomputes the spread in the browser with the same rules as
`compute.py`. The footer shows a check that the browser engine reproduces `compute.py` for
every base case. Open the file directly, or serve it with GitHub Pages (see below).
`site/template.html` is the source; `site/artifact.html` is the same page without the
document wrapper.

## Daily time series

`.github/workflows/token-spread-daily.yml` runs fetch + compute every day at 06:17 UTC and
commits the snapshot. `report.md` is regenerated on Mondays and on manual runs.

Why daily: Silicon Data's free page and OpenRouter's API expose only **current** values, so the
daily snapshot is the only way to get their history. InferenceX keeps its own history and
changes in steps every few weeks. Unchanged files are not re-copied, so `snapshots/` grows
slowly.

The job also rebuilds `site/index.html` daily. To publish it on GitHub Pages, set
Settings → Pages → Source to "GitHub Actions" and add a repository variable
`ENABLE_PAGES=true`.

GitHub runs scheduled workflows only from the default branch, so the job starts once this
is merged into the default branch. It can also be started manually from the Actions tab.

## Known limitations

See the "Data gaps and caveats" section of `report.md`. In short: benchmark throughput ≠
production throughput, 3:1 and 10:1 ratios are interpolated, configurations are not matched
across GPUs, prices are list prices, and rental is neocloud on-demand.
