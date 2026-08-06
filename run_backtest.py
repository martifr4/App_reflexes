#!/usr/bin/env python3
"""Single entry point for the App Reflexes crypto research backtest.

Usage:
    python run_backtest.py                         # use config/default.yaml
    python run_backtest.py --config myconfig.yaml
    python run_backtest.py --combiner rules        # override combiner
    python run_backtest.py --no-cache              # force fresh data pull
    python run_backtest.py --null-mode shuffle     # null test mode

Outputs (under reports/):
    metrics.csv        full-period + IS/OOS + benchmark metrics
    equity_curve.png   strategy vs BTC buy&hold vs equal-weight
    summary.txt        human-readable summary (also printed to stdout)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from reflexes.config import load_config
from reflexes.data.ingest import load_universe, to_panel
from reflexes.features.assemble import build_feature_panel
from reflexes.decision.base import make_combiner
from reflexes.portfolio.risk import apply_risk_limits
from reflexes.backtest.engine import run_backtest
from reflexes.backtest.metrics import compute_metrics, metrics_table
from reflexes.backtest.benchmarks import buy_and_hold_weights, equal_weight_weights
from reflexes.backtest.walkforward import split_is_oos
from reflexes.backtest.null_test import run_null_test, null_percentile

REPORTS = Path(__file__).resolve().parent / "reports"


def _asset_returns(frames) -> pd.DataFrame:
    """Daily close-to-close simple returns per asset (for risk vol targeting)."""
    close = to_panel(frames, "close")
    return close.pct_change().fillna(0.0)


def _combiner_raw_weights(cfg, signal_panel) -> pd.DataFrame:
    combiner = make_combiner(cfg)
    # Only decide on dates where every asset has a fully-formed signal row.
    common_index = None
    for sf in signal_panel.values():
        idx = sf.dropna(how="any").index
        common_index = idx if common_index is None else common_index.intersection(idx)
    weights = combiner.run(signal_panel, dates=common_index)
    return weights.fillna(0.0), combiner


def _report_block(returns, equity=None, turnover=None, costs=None) -> dict:
    return compute_metrics(returns, equity=equity, turnover=turnover, costs=costs)


def main() -> int:
    ap = argparse.ArgumentParser(description="App Reflexes crypto backtest")
    ap.add_argument("--config", default=None, help="Path to YAML config")
    ap.add_argument("--combiner", default=None, choices=["rules", "llm"], help="Override combiner")
    ap.add_argument("--no-cache", action="store_true", help="Force fresh data pull")
    ap.add_argument("--null-mode", default="random", choices=["random", "shuffle"])
    ap.add_argument("--skip-null", action="store_true", help="Skip the null test")
    ap.add_argument("--no-plot", action="store_true", help="Skip the equity-curve plot")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.combiner:
        cfg["decision"]["combiner"] = args.combiner
    REPORTS.mkdir(exist_ok=True)

    combiner_name = cfg["decision"]["combiner"]
    print(f"[run] combiner={combiner_name}  universe={cfg['data']['universe']}")
    if combiner_name == "llm":
        print("[run] NOTE: LLM combiner issues one API call per rebalance date. This is "
              "slow/costly over long horizons and returns FLAT (flagged) if no API key.")

    # 1. Data
    frames = load_universe(cfg, use_cache=not args.no_cache)
    if not frames:
        print("[run] ERROR: no data loaded.")
        return 1
    for a, df in frames.items():
        rep = df.attrs.get("ingest_report", {})
        print(f"[data] {a}: {len(df)} bars  filled={rep.get('n_filled', '?')} "
              f"still_missing={rep.get('n_still_missing', '?')}")

    asset_returns = _asset_returns(frames)

    # 2. Features -> canonical signals
    signal_panel = build_feature_panel(frames, cfg)

    # 3. Decision -> raw target weights
    raw_weights, combiner = _combiner_raw_weights(cfg, signal_panel)
    if raw_weights.empty:
        print("[run] ERROR: no decision dates (insufficient warmup?).")
        return 1

    # 4. Risk -> risk-managed target weights
    risked = apply_risk_limits(raw_weights, asset_returns, cfg)

    # 5. Backtest strategy + benchmarks (same engine, same costs)
    strat = run_backtest(frames, risked, cfg, verify=True)
    print(f"[backtest] lookahead assertion passed; {len(strat.returns)} bars.")

    assets = list(risked.columns)
    idx = risked.index
    bh_w = buy_and_hold_weights(idx, assets, hold_asset="BTC")
    ew_w = equal_weight_weights(idx, assets)
    bh = run_backtest(frames, bh_w, cfg, verify=True)
    ew = run_backtest(frames, ew_w, cfg, verify=True)

    oos_start = cfg["backtest"]["oos_start"]

    def is_oos_metrics(res):
        full = _report_block(res.returns, res.equity, res.turnover, res.costs)
        is_r, oos_r = split_is_oos(res.returns, oos_start)
        is_e, oos_e = split_is_oos(res.equity, oos_start)
        is_t, oos_t = split_is_oos(res.turnover, oos_start)
        is_c, oos_c = split_is_oos(res.costs, oos_start)
        return {
            "full": full,
            "IS": _report_block(is_r, is_e, is_t, is_c),
            "OOS": _report_block(oos_r, oos_e, oos_t, oos_c),
        }

    strat_m = is_oos_metrics(strat)
    bh_m = is_oos_metrics(bh)
    ew_m = is_oos_metrics(ew)

    # 6. Null test (on OOS)
    null_summary = None
    if not args.skip_null:
        null_summary = run_null_test(frames, raw_weights, asset_returns, cfg, mode=args.null_mode)
        strat_oos_sharpe = strat_m["OOS"]["sharpe"]
        pct = null_percentile(null_summary, strat_oos_sharpe)
        null_summary["strategy_oos_sharpe"] = strat_oos_sharpe
        null_summary["strategy_beats_null_pct"] = pct

    # 7. Assemble + write report
    table = metrics_table({
        f"STRAT[{combiner_name}] full": strat_m["full"],
        f"STRAT[{combiner_name}] IS": strat_m["IS"],
        f"STRAT[{combiner_name}] OOS": strat_m["OOS"],
        "BTC B&H full": bh_m["full"],
        "BTC B&H IS": bh_m["IS"],
        "BTC B&H OOS": bh_m["OOS"],
        "EqualWt full": ew_m["full"],
        "EqualWt IS": ew_m["IS"],
        "EqualWt OOS": ew_m["OOS"],
    })
    table.to_csv(REPORTS / "metrics.csv")

    summary = _format_summary(cfg, combiner_name, table, null_summary, strat, oos_start)
    (REPORTS / "summary.txt").write_text(summary)
    print("\n" + summary)

    if not args.no_plot:
        _plot_equity(strat, bh, ew, combiner_name, oos_start)
        print(f"[run] wrote {REPORTS / 'equity_curve.png'}")

    print(f"[run] wrote {REPORTS / 'metrics.csv'} and {REPORTS / 'summary.txt'}")
    return 0


def _fmt(v):
    if isinstance(v, float):
        if np.isnan(v):
            return "  nan"
        return f"{v:.3f}"
    return str(v)


def _format_summary(cfg, combiner_name, table, null_summary, strat, oos_start) -> str:
    lines = []
    lines.append("=" * 78)
    lines.append("APP REFLEXES — BACKTEST SUMMARY")
    lines.append("=" * 78)
    lines.append(f"combiner         : {combiner_name}")
    lines.append(f"universe         : {cfg['data']['universe']}")
    lines.append(f"execution        : {cfg['backtest']['execution']} (decide close[T], "
                 f"execute price[T+1], hold to [T+2] — no same-bar)")
    lines.append(f"costs            : {cfg['backtest']['cost_bps']} bps + "
                 f"{cfg['backtest']['slippage_bps']} bps slippage per unit turnover")
    lines.append(f"OOS holdout      : >= {oos_start}")
    lines.append(f"total costs paid : {strat.meta['total_costs_fraction']:.4f} "
                 f"(fraction of capital, cumulative)")
    lines.append("-" * 78)
    key_rows = ["cagr", "sharpe", "sortino", "max_drawdown", "hit_rate",
                "win_loss_ratio", "turnover_annual", "total_costs"]
    header = "metric".ljust(16) + "".join(c[:14].ljust(15) for c in table.columns)
    lines.append(header)
    for row in key_rows:
        cells = "".join(_fmt(table.loc[row, c]).ljust(15) for c in table.columns)
        lines.append(row.ljust(16) + cells)
    lines.append("-" * 78)
    if null_summary is not None:
        lines.append(f"NULL TEST ({null_summary['mode']}, n={null_summary['n']}):")
        lines.append(f"  null OOS Sharpe  mean={null_summary['oos_sharpe_mean']:.3f}  "
                     f"std={null_summary['oos_sharpe_std']:.3f}  "
                     f"p95={null_summary['oos_sharpe_p95']:.3f}  "
                     f"max={null_summary['oos_sharpe_max']:.3f}")
        lines.append(f"  strategy OOS Sharpe = {null_summary['strategy_oos_sharpe']:.3f}")
        pct = null_summary['strategy_beats_null_pct']
        lines.append(f"  strategy beats {pct*100:.0f}% of null runs "
                     f"({'ABOVE' if pct >= 0.95 else 'NOT clearly above'} the 95th pct of noise)")
    lines.append("=" * 78)
    lines.append("Read HONEST_ASSESSMENT.md before trusting any of these numbers.")
    return "\n".join(lines)


def _plot_equity(strat, bh, ew, combiner_name, oos_start):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(strat.equity.index, strat.equity.values, label=f"Strategy [{combiner_name}]", lw=1.6)
    ax.plot(bh.equity.index, bh.equity.values, label="BTC buy & hold", lw=1.1, alpha=0.8)
    ax.plot(ew.equity.index, ew.equity.values, label="Equal weight", lw=1.1, alpha=0.8)
    oos_ts = pd.Timestamp(oos_start)
    if strat.equity.index.tz is not None:
        oos_ts = oos_ts.tz_localize(strat.equity.index.tz)
    ax.axvline(oos_ts, color="k", ls="--", lw=0.8, alpha=0.6)
    ax.text(oos_ts, ax.get_ylim()[1], " OOS holdout →", va="top", fontsize=8)
    ax.set_yscale("log")
    ax.set_ylabel("Equity (log scale)")
    ax.set_title("App Reflexes — strategy vs benchmarks (net of costs)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(REPORTS / "equity_curve.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
