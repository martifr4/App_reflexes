# App Reflexes — modular crypto trading research

A research system for asking one honest question: **does an LLM-driven, multi-signal
daily strategy have any real out-of-sample edge over simple benchmarks, after costs?**

Correctness and honest evaluation are prioritized over impressive-looking returns. If
the strategy doesn't beat buy-and-hold after costs, the report says so plainly — see
[`HONEST_ASSESSMENT.md`](HONEST_ASSESSMENT.md).

## Data source

**Coinbase Exchange REST API** (`https://api.exchange.coinbase.com`) — free, keyless,
and returns real daily OHLCV *with volume*. It was chosen after checking the
alternatives from a live environment:

| Source | Verdict |
|---|---|
| Coinbase Exchange | ✅ Free, no key, full daily OHLCV incl. volume, paginates to multi-year history |
| Binance | ❌ HTTP 451 — geo-restricted from this environment |
| CoinGecko (free `/ohlc`) | ❌ No volume, and silently downsamples to multi-day candles beyond 30 days |

No paid data dependency is used. The universe (BTC, ETH, SOL by default) is explicit and
configurable in `config/default.yaml`.

## Architecture

Each module is independently testable and swappable — these are software modules, not
autonomous agents.

```
config/default.yaml          all tunables (universe, features, costs, risk, splits)
run_backtest.py              single entry point
src/reflexes/
  data/ingest.py             Coinbase OHLCV -> Parquet cache; UTC align; gap-fill; survivorship
  features/price.py          returns, momentum(12-1), MA relationships, realized vol, ATR, drawdown
  features/volume.py         volume trend vs baseline, volume-price divergence, participation
  features/news.py           QUARANTINED sentiment — neutral+flagged unless timestamped news given
  features/assemble.py       collapse raw features into 5 canonical signals in [-1, 1]
  decision/rules.py          transparent rules combiner
  decision/llm.py            LLM-reasoning combiner (swappable; FLAT+flagged w/o API key)
  portfolio/risk.py          per-asset cap, gross cap, vol targeting
  backtest/engine.py         next-bar execution, costs, slippage, lookahead assertions
  backtest/metrics.py        CAGR, Sharpe, Sortino, maxDD, hit rate, win/loss, turnover, costs
  backtest/benchmarks.py     BTC buy&hold + equal-weight (same engine & costs)
  backtest/walkforward.py    in-sample / out-of-sample split
  backtest/null_test.py      shuffled / random-signal noise baseline
tests/                       unit tests per module (no network needed)
reports/                     generated: metrics.csv, equity_curve.png, summary.txt
notebooks/report.ipynb       results notebook
```

## Quickstart

```bash
pip install -r requirements.txt

# Full run: rules combiner, benchmarks, IS/OOS split, null test, plot
python run_backtest.py

# Options
python run_backtest.py --combiner rules        # or: llm  (needs ANTHROPIC_API_KEY)
python run_backtest.py --null-mode shuffle      # fairer null (preserves weight profile)
python run_backtest.py --no-cache               # force a fresh data pull
python run_backtest.py --skip-null --no-plot    # fast metrics-only run

# Tests (offline; synthetic data)
python -m pytest tests/ -q
```

Outputs land in `reports/`: `metrics.csv`, `equity_curve.png`, `summary.txt`.

## Key design choices (the ones that protect honesty)

- **No same-bar execution.** A weight decided at the close of bar `T` is executed at the
  *next* bar's price and held one full bar (`held_weight = target.shift(2)`). The engine
  asserts this alignment (`assert_no_lookahead`), so a refactor can't silently reintroduce
  same-bar trading. A naive 1-bar close-to-close lag would enter on the decision bar — that
  is exactly the lookahead this refuses.
- **Strictly causal features.** Every feature at `T` uses only data at/before `T`;
  `test_features.py` proves that appending future bars doesn't change past feature values.
- **News is quarantined.** Off by default. When enabled, only headlines timestamped
  strictly before the decision date are used; missing/untimestamped news yields a neutral,
  *flagged* signal rather than a fabricated one.
- **Benchmarks pay the same costs.** BTC buy-and-hold and equal-weight run through the same
  execution + cost model — no benchmark gets a free pass.
- **Null test.** The whole pipeline is re-run on shuffled/random signals to show what
  "no edge" looks like.

## The LLM combiner

`decision/llm.py` hands the canonical signal frame for one date to a Claude model and asks
for a target weight + rationale per asset, using structured outputs so the reply always
parses. It is a drop-in alternative to the rules combiner. Without `ANTHROPIC_API_KEY` (or
an `ant` profile) it returns FLAT weights and flags `llm_configured=False` — it never
fabricates positions. Note: one API call per rebalance date makes a multi-year LLM backtest
slow and costly; use it on a bounded window to compare against the rules combiner.
