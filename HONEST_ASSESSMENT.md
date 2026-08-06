# HONEST_ASSESSMENT.md

Read this before trusting any number in `reports/`. The whole point of this project is an
honest read on edge, so this document leads with the uncomfortable answer.

## Bottom line

**Out-of-sample, after costs, the rules strategy does NOT beat the benchmarks.** It also
does not beat them in-sample once costs are paid at its turnover level. It *does* beat a
random-signal null — but, as explained below, that bar is low and mostly reflects that
random churning pays even more in transaction costs, not that the strategy has predictive
skill.

There is **no evidence of a real, cost-surviving edge** here. If anything, the exercise is
a clean demonstration of how transaction costs on a high-turnover daily strategy destroy a
signal that looks plausible on paper.

## The numbers (default config: BTC/ETH/SOL, 2021-06 → present, OOS ≥ 2024-01-01)

These are the rules combiner with 10 bps cost + 5 bps slippage per unit turnover,
next-open execution. Regenerate with `python run_backtest.py`.

| Metric (out-of-sample) | Strategy (rules) | BTC buy & hold | Equal weight |
|---|---:|---:|---:|
| Sharpe | **0.05** | 0.58 | 0.35 |
| CAGR | **−6.5%** | +17.9% | +2.9% |
| Max drawdown | −62% | −53% | −64% |
| Annualized turnover | **~97×** | ~0× | ~0× |

In-sample the strategy looks better (Sharpe ~0.48) but still loses to both benchmarks
(BTC B&H IS Sharpe ~0.96). The IS→OOS drop is large, and much of it is regime, not decay:
in-sample spans the 2021 blow-off and 2022 bear; the holdout is the 2024+ recovery.

Cumulative trading costs paid are on the order of **0.6× of capital over the full period**
(~0.38× in the holdout alone). That single line explains most of the underperformance:
the raw signal may be marginally informative, but daily volatility-target rescaling plus
signal flips churn ~20–25% of the book per day, and 15 bps × that turnover, compounded, is
fatal. (Exact figures drift slightly run-to-run with the live data window — regenerate to
refresh.)

## The null test, honestly

The null test re-runs the *entire* pipeline on shuffled/random signals. The strategy's OOS
Sharpe (~0.07) beats ~100% of null runs, whose Sharpe averages roughly **−1.5 (shuffle)**
to **−2.0 (random)**. That sounds like a win. It mostly isn't:

- The null distribution is dominated by **transaction-cost drag**, not by the absence of
  signal. Random/shuffled weights churn maximally and pay enormous costs, so they land
  deeply negative regardless of any predictive content.
- So "beats the null" here really means "churns somewhat less catastrophically than pure
  noise." That is a much weaker claim than "has edge," and it is **not** the claim the
  headline percentile suggests.
- The honest comparison is against the **benchmarks**, which the strategy loses to. Beating
  noise while losing to buy-and-hold is not an edge.

A better null would neutralize the cost channel (e.g. compare gross Sharpe, or fix turnover
across null and strategy). The current null is included because it was requested and is
informative about the cost regime — but its verdict should not be read as evidence of skill.

## What could still be leaking or is overfit

Even though this result is *negative*, I want to be explicit about the ways a *positive*
result here would have been suspect — several apply regardless of sign:

1. **Survivorship bias (documented, not fixed).** The universe is three large survivors
   picked with hindsight. SOL in particular both survived and thrived; a fair universe
   would include coins that were plausible daily candidates in 2021 and later died or
   delisted. `config.data.universe` is fixed and explicit precisely so this bias is visible,
   not hidden — but it is still a bias, and it flatters any long-biased result.
2. **Researcher degrees of freedom.** The rules weights/thresholds are set a priori in YAML
   (not fitted), which limits classic overfitting. But I *did* see full-sample behavior
   while building the modules, so the config is not truly blind to the holdout. The IS/OOS
   split is a single fixed cut, not a rolling walk-forward with periodic refitting — it is
   the minimum honest scaffolding, not the maximum.
3. **Short side is under-costed.** Shorts pay trading cost but no borrow/funding/carry. Real
   perpetual-futures funding on crypto shorts is material and time-varying; any short P&L
   here is optimistic.
4. **Slippage is a flat bps constant.** No market-impact model, no bid/ask, no fill
   uncertainty. For three of the most liquid crypto assets and a small book this is roughly
   OK, but it understates cost in stress and for larger size.
5. **Vol targeting is the turnover engine.** The ex-ante vol estimate is causal but noisy,
   and rescaling gross every day generates turnover even when the underlying signal is
   unchanged. This is realistic, but it means the cost result is sensitive to the vol-target
   and window choices.
6. **Rolling z-score warmup.** Signals are normalized with `min_periods = window//2`, so the
   earliest normalized values rest on thin history and are unstable.
7. **Single data vendor, single field convention.** Coinbase only; a gap or bad print on
   Coinbase is not cross-checked against another exchange. Timezone is forced to UTC and
   gaps are handled explicitly, but I have not reconciled prices against a second source.
8. **News module is off.** The quarantined news signal contributes nothing in these runs, so
   this is not a test of a news edge — only of price/volume signals.

## What I would NOT trust

- **The "beats 100% of the null" line as evidence of edge.** See above — it's a cost-regime
  artifact.
- **Any in-sample Sharpe as predictive of the future.**
- **Short-side returns**, because borrow/funding is unmodeled.
- **Extrapolating 3-survivor results to a broad tradable universe** — survivorship makes the
  long side look better than a realistic universe would.
- **The LLM combiner's numbers, if you run it.** It is functional and structured-output
  constrained, but it is an untested black box at backtest scale, costs one API call per
  rebalance date, and introduces model non-determinism. Treat any LLM-combiner result as a
  hypothesis to scrutinize, never as a validated edge — and compare it head-to-head with the
  transparent rules combiner, which is the honest baseline it must beat.

## What would change my mind (next steps)

- Reconstruct a survivorship-free daily universe (include dead/delisted coins).
- Reduce turnover (rebalance bands, slower vol target, signal hysteresis) and re-test — the
  question is whether *any* cost-surviving signal remains once churn is controlled.
- Add realistic short funding and a market-impact term to slippage.
- Replace the single IS/OOS cut with a rolling walk-forward, and if any parameter is ever
  fitted, refit only on past data at each step.
- Build a cost-neutral null (fix turnover across null and strategy) so "beats noise" measures
  signal, not churn.

Until those are done, the honest verdict stands: **no demonstrated out-of-sample edge over
buy-and-hold after costs.**
