"""Join prices, throughput and rental data and compute the token spread.

Outputs (outputs/):
  spread_summary.csv   one row per model × GPU × precision at base assumptions
  sensitivity.csv      base cases across utilization × input:output ratio
  provider_spread.csv  base cases, one row per OpenRouter provider
  operating_points.csv the benchmark point chosen for every model/GPU/precision/sequence
  breakeven_throughput.csv  tokens/s per GPU each model needs for its price to cover rent;
                       price-only models (closed, or open-weight without comparable
                       benchmarks) and benchmarked open-weight models (with their
                       measured throughput for comparison)
  price_comparison.csv list/blended prices of every model, open and closed
and a dated copy in snapshots/ (see snapshot()).

Formula (per model, GPU, precision, provider):
  blended_price_per_Mtok   = (r·in_price + 1·out_price) / (r + 1)       r = input:output ratio
  tokens_per_gpu_hour      = throughput_tok_s_per_gpu · 3600 · utilization
  implied_revenue_per_hour = tokens_per_gpu_hour / 1e6 · blended_price_per_Mtok
  token_spread             = implied_revenue_per_hour − rental_per_gpu_hour
  spread_ratio             = implied_revenue_per_hour / rental_per_gpu_hour
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
DATA, OUT, SNAP = ROOT / "data", ROOT / "outputs", ROOT / "snapshots"


def load():
    cfg = yaml.safe_load(open(ROOT / "assumptions.yaml"))
    prices = pd.read_csv(DATA / "api_prices.csv")
    tput = pd.read_csv(DATA / "throughput.csv")
    rental = pd.read_csv(DATA / "gpu_rental.csv")
    return cfg, prices, tput, rental


# --- throughput -------------------------------------------------------------

def eligible(tput: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    t = tput.copy()
    if not cfg["allow_speculative_decoding"]:
        t = t[t.spec_method == "none"]
    if not cfg["allow_disaggregated_multinode"]:
        t = t[~t.disagg.astype(bool) & ~t.is_multinode.astype(bool)]
    return t


def operating_points(tput: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """For each model/GPU/precision/sequence pick
    - 'floor': max tput_per_gpu with median interactivity >= floor
    - 'max':   max tput_per_gpu overall (upper bound)."""
    floor = cfg["interactivity_floor_tok_s_per_user"]
    rows = []
    for key, g in eligible(tput, cfg).groupby(["model_key", "hardware", "precision", "isl", "osl"]):
        for op, sub in [("floor", g[g.median_intvty >= floor]), ("max", g)]:
            if sub.empty:
                continue
            best = sub.loc[sub.tput_per_gpu.idxmax()]
            # Did the benchmark sweep stop while still well above the speed floor?
            # Then a higher concurrency would likely have given more throughput.
            sweep = g[(g.framework == best.framework) & (g.spec_method == best.spec_method)
                      & (g.disagg == best.disagg) & (g.num_gpus == best.num_gpus)]
            edge = bool(best.conc >= sweep.conc.max() and best.median_intvty > 1.15 * max(floor, 1))
            rows.append({
                "model_key": key[0], "gpu": key[1], "precision": key[2],
                "isl": key[3], "osl": key[4], "measured_ratio": key[3] / key[4],
                "op_point": op, "tput_per_gpu": best.tput_per_gpu,
                "median_intvty": best.median_intvty, "framework": best.framework,
                "spec_method": best.spec_method, "disagg": best.disagg,
                "conc": best.conc, "num_gpus": best.num_gpus,
                "bench_date": best.bench_date, "source_url": best.source_url,
                "sweep_edge": edge,
            })
    return pd.DataFrame(rows)


def tput_at_ratio(ops: pd.DataFrame, ratio: float):
    """Throughput at an input:output ratio from the measured sequence points.
    Linear in log(ratio) between measured ratios; flat outside. Returns
    (tput, estimate_flag, basis_text, source_urls)."""
    pts = ops.sort_values("measured_ratio")
    xs, ys = np.log(pts.measured_ratio.values), pts.tput_per_gpu.values
    urls = ";".join(pts.source_url.astype(str))
    x = math.log(ratio)
    for r, row in zip(xs, pts.itertuples()):
        if abs(r - x) < 1e-9:
            return row.tput_per_gpu, False, f"measured {row.isl}/{row.osl}", row.source_url
    if len(xs) == 0:
        return np.nan, True, "no data", ""
    if x <= xs[0] or x >= xs[-1]:
        i = 0 if x <= xs[0] else -1
        p = pts.iloc[i]
        return ys[i], True, f"held flat at nearest measured {p.isl}/{p.osl}", p.source_url
    y = float(np.interp(x, xs, ys))
    j = int(np.searchsorted(xs, x))
    a, b = pts.iloc[j - 1], pts.iloc[j]
    return y, True, f"log-interp {a.isl}/{a.osl}–{b.isl}/{b.osl}", urls


# --- prices & rental -------------------------------------------------------

def blended(prices: pd.DataFrame, ratio: float) -> pd.Series:
    return (ratio * prices.input_price_per_Mtok + prices.output_price_per_Mtok) / (ratio + 1)


def price_stats(prices: pd.DataFrame, ratio: float) -> dict:
    b = blended(prices, ratio)
    return {"n_providers": len(b), "price_min": b.min(), "price_median": b.median(),
            "price_max": b.max()}


def rental_lookup(rental: pd.DataFrame, cfg: dict) -> dict:
    out = {}
    for gpu, g in rental.groupby("gpu"):
        base = g[g.series == cfg["rental_base_series"]].price_per_gpu_hour
        market = g[~g.series.str.contains("owner_tco")].price_per_gpu_hour
        out[gpu] = {"rental_base": base.iloc[0] if len(base) else np.nan,
                    "rental_low": market.min(), "rental_high": market.max(),
                    "owner_tco": g[g.series.str.contains("owner_tco")].price_per_gpu_hour.min()}
    return out


# --- main computation ------------------------------------------------------

def cases(cfg: dict):
    for m in cfg["models"]:
        for gpu in cfg["gpus"]:
            if gpu in m["base_precision"]:  # some models have no benchmark on every GPU
                yield m, gpu, m["base_precision"][gpu], "base"
        for v in m.get("variants", []):
            yield m, v["gpu"], v["precision"], "variant"


def compute(cfg, prices, tput, rental):
    prices = prices[~prices.provider.isin(cfg.get("exclude_providers") or [])]
    prices = prices.dropna(subset=["input_price_per_Mtok", "output_price_per_Mtok"])
    ops = operating_points(tput, cfg)
    rent = rental_lookup(rental, cfg)
    stat = cfg["price_statistic"]
    u0, r0 = cfg["utilization_base"], cfg["io_ratio_base"]

    def evaluate(m, gpu, prec, ratio, util):
        sel = ops[(ops.model_key == m["key"]) & (ops.gpu == gpu) & (ops.precision == prec)]
        res = {}
        for op in ("floor", "max"):
            t, est, basis, urls = tput_at_ratio(sel[sel.op_point == op], ratio)
            res[op] = dict(tput=t, est=est, basis=basis, urls=urls)
        return sel, res

    summary, sens, prov = [], [], []
    for m, gpu, prec, case in cases(cfg):
        p = prices[prices.model_key == m["key"]]
        sel, res = evaluate(m, gpu, prec, r0, u0)
        ps = price_stats(p, r0)
        R = rent.get(gpu, {})
        tok_h = res["floor"]["tput"] * 3600 * u0
        rev = {k: tok_h / 1e6 * ps[f"price_{k}"] for k in ("min", "median", "max")}
        rev_max_tput = res["max"]["tput"] * 3600 * u0 / 1e6 * ps[f"price_{stat}"]
        rev100 = res["floor"]["tput"] * 3600 / 1e6 * ps[f"price_{stat}"]
        fl = sel[(sel.op_point == "floor")]
        summary.append({
            "model": m["key"], "kind": m["kind"], "gpu": gpu, "precision": prec, "case": case,
            "io_ratio": r0, "utilization": u0, **ps,
            "tput_per_gpu": res["floor"]["tput"], "tput_per_gpu_max": res["max"]["tput"],
            "tput_basis": res["floor"]["basis"], "estimate": res["floor"]["est"],
            "tokens_per_gpu_hour": tok_h,
            "revenue": rev[stat], "revenue_pmin": rev["min"], "revenue_pmax": rev["max"],
            "revenue_max_tput": rev_max_tput,
            "rental": R.get("rental_base"), "rental_low": R.get("rental_low"),
            "rental_high": R.get("rental_high"), "owner_tco": R.get("owner_tco"),
            "spread": rev[stat] - R.get("rental_base", np.nan),
            "spread_ratio": rev[stat] / R.get("rental_base", np.nan),
            "spread_ratio_max_tput": rev_max_tput / R.get("rental_base", np.nan),
            "breakeven_utilization": R.get("rental_base", np.nan) / rev100 if rev100 else np.nan,
            "frameworks": ",".join(sorted(set(fl.framework.astype(str)))),
            "bench_dates": ",".join(sorted(set(fl.bench_date.astype(str)))),
            "source_urls": res["floor"]["urls"],
        })
        if case == "base":
            for ratio in cfg["io_ratio_sensitivity"]:
                _, rr = evaluate(m, gpu, prec, ratio, None)
                pr = price_stats(p, ratio)[f"price_{stat}"]
                for util in cfg["utilization_sensitivity"]:
                    for op in ("floor", "max"):
                        revv = rr[op]["tput"] * 3600 * util / 1e6 * pr
                        sens.append({"model": m["key"], "gpu": gpu, "precision": prec,
                                     "op_point": op, "io_ratio": ratio, "utilization": util,
                                     "blended_price": pr, "tput_per_gpu": rr[op]["tput"],
                                     "tput_basis": rr[op]["basis"], "estimate": rr[op]["est"],
                                     "revenue": revv, "rental": R.get("rental_base"),
                                     "spread": revv - R.get("rental_base", np.nan),
                                     "spread_ratio": revv / R.get("rental_base", np.nan)})
            for pr_row, bp in zip(p.itertuples(), blended(p, r0)):
                revv = tok_h / 1e6 * bp
                prov.append({"model": m["key"], "gpu": gpu, "precision": prec,
                             "provider": pr_row.provider, "quantization": pr_row.quantization,
                             "input_price": pr_row.input_price_per_Mtok,
                             "output_price": pr_row.output_price_per_Mtok,
                             "blended_price": bp, "revenue": revv,
                             "rental": R.get("rental_base"),
                             "spread": revv - R.get("rental_base", np.nan),
                             "spread_ratio": revv / R.get("rental_base", np.nan)})
    return pd.DataFrame(summary), pd.DataFrame(sens), pd.DataFrame(prov), ops


# --- price-only models: breakeven throughput and price comparison --------------
# "price-only" = closed models plus open-weight models without fixed-length benchmarks.

def breakeven_tput(rental: float, price_per_mtok: float, util: float) -> float:
    """Tokens/s per GPU at which revenue = rent."""
    return rental / (3600 * util * price_per_mtok / 1e6)


def closed_analysis(cfg, closed: pd.DataFrame, summary: pd.DataFrame, rental: pd.DataFrame):
    r0, u0 = cfg["io_ratio_base"], cfg["utilization_base"]
    rent = rental_lookup(rental, cfg)
    base = summary[summary.case == "base"]
    be_rows, price_rows = [], []
    for key, g in closed.groupby("model_key", sort=False):
        f = g.iloc[0]
        lp = (r0 * f.list_input_price_per_Mtok + f.list_output_price_per_Mtok) / (r0 + 1)
        ep = blended(g, r0)
        price_rows.append({"model": key, "weights": f.weights, "analysis": "price-only",
                           "lab": f.lab, "tier": f.tier,
                           "input_price": f.list_input_price_per_Mtok,
                           "output_price": f.list_output_price_per_Mtok,
                           "blended_price": lp, "endpoint_blended_min": ep.min(),
                           "endpoint_blended_max": ep.max(), "n_endpoints": len(g),
                           "price_basis": "OpenRouter list price", "source_url": f.list_source_url})
        for gpu in cfg["gpus"]:
            R = rent[gpu]["rental_base"]
            be = breakeven_tput(R, lp, u0)
            op = base[base.gpu == gpu].dropna(subset=["tput_per_gpu"])
            top = op.loc[op.tput_per_gpu.idxmax()] if len(op) else None
            be_rows.append({"model": key, "weights": f.weights, "analysis": "price-only",
                            "lab": f.lab, "gpu": gpu,
                            "io_ratio": r0, "utilization": u0, "blended_price": lp, "rental": R,
                            "breakeven_tput_per_gpu": be,
                            "breakeven_tput_per_gpu_full_util": breakeven_tput(R, lp, 1.0),
                            "measured_tput_per_gpu": np.nan,
                            "open_models_at_or_above": int((op.tput_per_gpu >= be).sum()),
                            "open_models_compared": len(op),
                            "fastest_open_model": None if top is None else top.model,
                            "fastest_open_tput": None if top is None else top.tput_per_gpu})
    for _, r in base.iterrows():
        be_rows.append({"model": r.model, "weights": "open", "analysis": "spread",
                        "lab": "open-weight", "gpu": r.gpu,
                        "io_ratio": r0, "utilization": u0, "blended_price": r.price_median,
                        "rental": r.rental,
                        "breakeven_tput_per_gpu": breakeven_tput(r.rental, r.price_median, u0),
                        "breakeven_tput_per_gpu_full_util": breakeven_tput(r.rental, r.price_median, 1.0),
                        "measured_tput_per_gpu": r.tput_per_gpu})
    for key, d in base.groupby("model", sort=False):
        f = d.iloc[0]
        price_rows.append({"model": key, "weights": "open", "analysis": "spread",
                           "lab": "open-weight", "tier": f.kind,
                           "input_price": np.nan, "output_price": np.nan,
                           "blended_price": f.price_median, "endpoint_blended_min": f.price_min,
                           "endpoint_blended_max": f.price_max, "n_endpoints": f.n_providers,
                           "price_basis": "median OpenRouter provider",
                           "source_url": "https://openrouter.ai/api/v1/models/{id}/endpoints"})
    pc = pd.DataFrame(price_rows).sort_values("blended_price", ascending=False)
    return pd.DataFrame(be_rows), pc


# --- snapshots ---------------------------------------------------------------

def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _latest_copy(name: str, before: str) -> Path | None:
    for d in sorted((x for x in SNAP.iterdir() if x.is_dir() and x.name < before), reverse=True):
        if (d / name).exists():
            return d / name
    return None


def snapshot(summary: pd.DataFrame, date: str):
    """snapshots/<date>/ gets each input/output file only if it differs from the
    latest stored copy (raw throughput is big and changes every few weeks).
    snapshots/timeseries.csv gets one row per base case per run date."""
    SNAP.mkdir(exist_ok=True)
    day = SNAP / date
    day.mkdir(exist_ok=True)
    files = [DATA / f for f in ("api_prices.csv", "api_prices_price_only.csv", "throughput.csv",
                                "gpu_rental.csv")] + \
            [OUT / f for f in ("spread_summary.csv", "sensitivity.csv", "provider_spread.csv",
                               "operating_points.csv", "breakeven_throughput.csv",
                               "price_comparison.csv")]
    files = [f for f in files if f.exists()]
    written = []
    for f in files:
        prev = _latest_copy(f.name, date)
        if prev is None or _digest(prev) != _digest(f):
            shutil.copy2(f, day / f.name)
            written.append(f.name)
        elif (day / f.name).exists():  # re-run same day with unchanged data
            (day / f.name).unlink()
    if not any(day.iterdir()):
        day.rmdir()
    cols = ["model", "gpu", "precision", "case", "io_ratio", "utilization", "price_median",
            "tput_per_gpu", "revenue", "rental", "spread", "spread_ratio",
            "breakeven_utilization", "bench_dates"]
    ts_path = SNAP / "timeseries.csv"
    row = summary[cols].assign(date=date)
    if ts_path.exists():
        ts = pd.read_csv(ts_path)
        ts = pd.concat([ts[ts.date != date], row], ignore_index=True)
    else:
        ts = row
    ts.sort_values(["date", "model", "gpu", "precision"]).to_csv(ts_path, index=False)
    print(f"snapshot {date}: {', '.join(written) or 'no changed files'}; timeseries rows={len(ts)}")


def main():
    cfg, prices, tput, rental = load()
    OUT.mkdir(exist_ok=True)
    summary, sens, prov, ops = compute(cfg, prices, tput, rental)
    summary.to_csv(OUT / "spread_summary.csv", index=False)
    sens.to_csv(OUT / "sensitivity.csv", index=False)
    prov.to_csv(OUT / "provider_spread.csv", index=False)
    ops.to_csv(OUT / "operating_points.csv", index=False)
    closed_path = DATA / "api_prices_price_only.csv"
    if closed_path.exists():
        be, pc = closed_analysis(cfg, pd.read_csv(closed_path), summary, rental)
        be.to_csv(OUT / "breakeven_throughput.csv", index=False)
        pc.to_csv(OUT / "price_comparison.csv", index=False)
    date = str(pd.read_csv(DATA / "api_prices.csv").retrieved_date.max()) or dt.date.today().isoformat()
    snapshot(summary, date)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(summary[["model", "gpu", "precision", "price_median", "tput_per_gpu", "revenue",
                       "rental", "spread", "spread_ratio", "breakeven_utilization"]].round(3))


if __name__ == "__main__":
    main()
