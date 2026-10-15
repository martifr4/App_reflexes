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

## Models

**Spread (benchmarked open-weight models):** every model InferenceX benchmarks at fixed
sequence lengths: Llama 3.3 70B, gpt-oss-120b, Qwen3.5-397B, MiniMax-M3, MiniMax-M2.5,
DeepSeek-R1, DeepSeek-V4-Pro, GLM-5 and Kimi-K2.5. The last three have B200 benchmarks only,
so they appear on B200 only. The list is `models` in `assumptions.yaml`. `inferencex_key`
picks one variant when an InferenceX name groups several (e.g. GLM-5 vs GLM-5.1).

**Price-only models:** closed models (Claude, GPT, Grok, Gemini, Meta Muse; `closed_models`) publish prices but
not hardware or throughput. Some open-weight models (`price_only_open_models`) have only
InferenceX *agentic* benchmarks, about 100:1 input:output with ~90% prefix-cache hits, whose
revenue depends on cached-input pricing and isn't comparable to the fixed-length tests, or no
runs yet. No spread is computed for either. Instead `compute.py` writes:

- `outputs/breakeven_throughput.csv`: the tokens/s per GPU each model needs for its price to
  cover the GPU's rent, `rent ÷ (3600 × utilization × blended price / 1e6)`. Price-only models
  get only this threshold. Benchmarked models also get their measured throughput, and
  measured ÷ needed = spread ratio.
- `outputs/price_comparison.csv`: blended prices of every model.

Price-only models use OpenRouter's model-level list price. Endpoint tiers (regional, priority,
flex) are kept as a range in `data/api_prices_price_only.csv`.

**Sweep edges.** InferenceX often stops a concurrency sweep while streams are still faster
than the speed floor. `outputs/operating_points.csv` marks such points `sweep_edge=True`;
their throughput at the floor is a lower bound.

## Electricity layer

The chain extends one step down: **electricity price → GPU-hour cost → rent → token revenue**.

```
kwh_per_gpu_hour       = all_in_kW × load_factor × PUE
power_cost_per_gpu_hour = kwh_per_gpu_hour × price_per_kWh
revenue_per_kWh        = implied_revenue_per_gpu_hour ÷ kwh_per_gpu_hour
```

- **All-in kW** per GPU (H100 1.37, B200 1.71) and the owner's total cost per GPU-hour come from
  SemiAnalysis's AI Cloud TCO model as published in InferenceX's open-source constants
  (`data/gpu_power.csv`). All-in includes the GPU's share of host CPU, memory and network.
- **PUE** (default 1.3) and **load factor** (default 0.8; measured GPU draw is 60–72% of TDP, 1.0 is the full-load upper bound) are in `assumptions.yaml`
  under `power`. Measured GPU power from newer InferenceX runs (`avg_power_w`) is reported in
  `outputs/power_chain.csv` as a cross-check; it is not used in the cost.
- **Electricity prices** (`data/electricity_prices.csv`): US states from EIA Electric Power
  Monthly table 5.6.A (latest month, by sector); European countries from Eurostat `nrg_pc_205`
  (non-household, 70–150 GWh/yr band, excl. VAT), converted to USD at the ECB rate. Regions
  are listed under `power.regions`.
- Outputs: `outputs/power_costs.csv` (power cost per GPU-hour by region) and
  `outputs/power_chain.csv` (per model and GPU: power, owner cost, rent, revenue, tokens and
  revenue per kWh).

## GPU rental firm economics

What does a firm that owns GPUs and rents them out (a neocloud) earn? Per calendar hour,
rented or idle:

```
capital_cost = capex × r ÷ (1 − (1 + r)^−years) ÷ 8760      # depreciation + financing
space_cost   = all_in_kW × colocation_$/kW-month × 12 ÷ 8760
full_cost    = capital_cost + space_cost + power_cost + operations
firm_profit  = rent × share_of_hours_rented − full_cost
```

Inputs are in `assumptions.yaml` → `rental_firm`; every published figure behind them (server
prices, depreciation life, cost of capital, CBRE colocation rates, operations, and CoreWeave's
Q2 2026 results as a reality check) is in `data/rental_firm_sources.csv` with a link.
Outputs: `outputs/firm_economics.csv` (cost stack, revenue, profit, margins, breakeven
occupancy, payback, across occupancy and depreciation-life sensitivities) and
`outputs/value_split.csv` (how one rented GPU-hour of token revenue splits between electricity,
space, operations, depreciation, financing, the landlord's profit and the inference provider's
profit, plus an owner that serves its own tokens).

## Profit ranking (open and closed models)

The website opens with a ranking of every model by profit per GPU-hour, for an owner that
serves the tokens itself:

```
profit = tokens/hour × blended price − full cost of owning the GPU (as above)
```

Open-weight models use measured throughput on `profit_ranking_open_gpu` (B200) and the median
provider price. Closed models have no public throughput or hardware, so both are assumed
(`assumptions.yaml` → `closed_infrastructure`, `closed_proxy_by_tier`): each lab's main serving
hardware, with a source link, is mapped to H100 or B200 (Trainium2 and TPUs count as B200-class),
and each model is assumed to produce as many tokens/s per GPU as a benchmarked open model of a
similar size tier. Revenue uses the closed model's list price. These rows are estimates; frontier
models are probably larger and slower than their proxies, so they read as upper bounds.
Output: `outputs/profit_ranking.csv`.

## Bitcoin mining comparison

For perspective, the site shows what the same GPU would earn mining bitcoin:

```
BTC per hour  = hash rate (TH/s) × 10^12 ÷ (difficulty × 2^32) × 3,600 × (block subsidy + fees per block)
revenue / h   = BTC per hour × BTC price
electricity/h = all-in kW (full load) × PUE × $/kWh
```

`fetch/fetch_bitcoin.py` pulls price, difficulty, hash rate and the last 144 blocks' fees from
mempool.space into `data/bitcoin_network.csv`; the subsidy follows the halving schedule.
Device hash rates are in `data/mining_hardware.csv`: H100 SXM ≈ 8.1 GH/s SHA-256d (half its
hashcat SHA-256 speed of 16.2 GH/s), B200 ≈ 9.0 GH/s (scaled by FP32 compute; no public
benchmark), and Bitmain's Antminer S23 (318 TH/s at 3.5 kW) as the ASIC reference. Output:
`outputs/bitcoin_mining.csv`. A GPU earns roughly 10^5–10^6 times more serving tokens than mining.

## Data sources

| File | Source | Fetch |
|---|---|---|
| `data/api_prices.csv` | [OpenRouter](https://openrouter.ai) `GET /api/v1/models/{id}/endpoints`: per-provider list prices and quantization | `fetch/fetch_openrouter.py` |
| `data/api_prices_price_only.csv` | OpenRouter `GET /api/v1/models` (list price) and `/models/{id}/endpoints` for each price-only model | `fetch/fetch_openrouter.py` |
| `data/electricity_prices.csv` | [EIA](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_a) table 5.6.A, [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_205/default/table) nrg_pc_205, [ECB](https://data.ecb.europa.eu/) EUR/USD | `fetch/fetch_power.py` |
| `data/gpu_power.csv` | InferenceX open-source GPU constants (SemiAnalysis TCO model) | `fetch/fetch_power.py` |
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
production throughput, the base 8:1 input:output mix is measured but 3:1 and 10:1 are
interpolated or held flat, cached-input prices (and the speed-up from prefix caching) are not
modelled although agent traffic is ~100:1 with ~90% cache hits, configurations are not matched
across GPUs, prices are list prices, and rental is Silicon Data's standardized index rather
than a term-contract price.

## Assumption review (2026-10-14)

Every assumption was re-checked against public sources. Changes made:

- input:output base 3:1 → 8:1 (OpenRouter: ~7:1 human traffic, ~15:1 average per request).
- load factor 1.0 → 0.8 (measured GPU draw 60–72% of TDP; host draw near constant). PUE 1.15 added
  to the sensitivity.
- cost of capital 9% → 10% (CoreWeave's Jun 2026 unsecured notes at 9.625% / 8.5%).
- xAI hardware H100 (Colossus 1) → B200-class (Colossus 2); Colossus 1 went to Anthropic in May 2026.
  grok-4.7 tier large → frontier (Musk-stated ~2.1T parameters).
- Added Meta Muse Spark 1.3 (closed, mid) and Muse Glimmer 30B (open, price-only).
- Gemini 4 Argon and 3.8 Flash prices are introductory and double on 1 Dec 2026 / 1 Jan 2027;
  noted on the site (the daily fetch follows the change).
- Wording: rental index description, reseller pricing, "spark spread", CoreWeave depreciation note.

Checked and kept: server prices, 6-year depreciation, $196/kW-month colocation (CBRE H1 2026 is
~4% higher but the figure could not be read), $0.10/h operations, 80% occupancy, 60% utilization,
30 tok/s floor, median price, fp8 base, PUE 1.3, all-in kW, EIA/Eurostat prices, CME futures,
closed-model tiers (Gemini Flash Lite stays "small": it is faster than gpt-oss-120b).
