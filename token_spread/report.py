"""Build report.md + charts/ from outputs/ (run compute.py first)."""
from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUT, CHARTS, DATA, SNAP = ROOT / "outputs", ROOT / "charts", ROOT / "data", ROOT / "snapshots"

# Reference palette (dataviz skill), categorical slots 1-3 in fixed order.
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
SERIES = {("h100", "base"): ("#2a78d6", "H100"),
          ("b200", "base"): ("#eb6834", "B200"),
          ("b200", "variant"): ("#1baf7a", "B200 fp4")}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "font.size": 10,
    "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
})


RATIO_TICKS = [0.125, 0.25, 0.5, 1, 2, 4, 8]


def log_ratio_axis(axis):
    """Log scale with plain 'n×' labels at powers of two, no minor labels."""
    axis.set_major_locator(matplotlib.ticker.FixedLocator(RATIO_TICKS))
    axis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}×"))
    axis.set_minor_formatter(matplotlib.ticker.NullFormatter())


# --- charts -----------------------------------------------------------------

def chart_spread(s: pd.DataFrame, path: Path, cfg):
    models = list(dict.fromkeys(s.model))
    keys = [k for k in SERIES if ((s.gpu == k[0]) & (s.case == k[1])).any()]
    h = 0.26
    fig, ax = plt.subplots(figsize=(8.5, 0.9 * len(models) + 1.6))
    for i, k in enumerate(keys):
        color, name = SERIES[k]
        d = s[(s.gpu == k[0]) & (s.case == k[1])].set_index("model").reindex(models)
        y = np.arange(len(models)) + (i - (len(keys) - 1) / 2) * h
        r = d.spread_ratio.values
        lo = d.revenue_pmin.values / d.rental.values
        hi = d.revenue_pmax.values / d.rental.values
        ok = ~np.isnan(r)
        lab = name if k != ("b200", "base") else "B200 (base precision)"
        if k == ("h100", "base"):
            lab = "H100 (base precision)"
        ax.barh(y[ok], r[ok], height=h - 0.04, color=color, label=lab, zorder=2)
        ax.errorbar(r[ok], y[ok], xerr=[r[ok] - lo[ok], hi[ok] - r[ok]], fmt="none",
                    ecolor=INK2, elinewidth=1, capsize=2.5, zorder=3)
        for yy, rr, hh in zip(y[ok], r[ok], hi[ok]):
            ax.text(hh * 1.04, yy, f"{rr:.2f}×", va="center", ha="left", fontsize=8,
                    color=INK2, zorder=4)
    ax.axvline(1, color=INK, lw=1, zorder=3)
    ax.text(1, len(models) - 0.45, " breakeven", fontsize=8, color=INK2, va="bottom")
    ax.set_yticks(range(len(models)), models)
    ax.invert_yaxis()
    ax.set_xscale("log")
    log_ratio_axis(ax.xaxis)
    ax.set_xlim(0.15, 12)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("implied revenue ÷ rental price  (log scale)")
    fig.suptitle("Token spread ratio by model and GPU", x=0.01, ha="left", fontweight="bold")
    ax.set_title(f"median provider price · {cfg['io_ratio_base']}:1 in:out · "
                 f"{cfg['utilization_base']:.0%} utilization · ≥{cfg['interactivity_floor_tok_s_per_user']} tok/s/user",
                 loc="left", fontweight="normal", fontsize=9, color=INK2)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=8)
    fig.text(0.01, 0.01, "Whiskers: cheapest → most expensive OpenRouter provider. "
             "Label = median-price ratio.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_sensitivity(sens: pd.DataFrame, path: Path, cfg):
    d = sens[sens.op_point == "floor"]
    models = list(dict.fromkeys(d.model))
    ncol = 3
    nrow = int(np.ceil(len(models) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(11, 3.2 * nrow), sharex=True, sharey=True)
    axes = np.atleast_1d(axes).ravel()
    r0 = cfg["io_ratio_base"]
    for ax, m in zip(axes, models):
        for gpu in ("h100", "b200"):
            color, name = SERIES[(gpu, "base")]
            g = d[(d.model == m) & (d.gpu == gpu)]
            if g.empty:
                continue
            band = g.groupby("utilization").spread_ratio.agg(["min", "max"])
            ax.fill_between(band.index, band["min"], band["max"], color=color, alpha=0.18, lw=0)
            base = g[g.io_ratio == r0].sort_values("utilization")
            ax.plot(base.utilization, base.spread_ratio, color=color, lw=2, label=f"{name} {r0}:1")
            ub = sens[(sens.op_point == "max") & (sens.model == m) & (sens.gpu == gpu)
                      & (sens.io_ratio == r0)].sort_values("utilization")
            ax.plot(ub.utilization, ub.spread_ratio, color=color, lw=1, ls=":")
        ax.axhline(1, color=INK, lw=1)
        ax.set_title(m, loc="left")
        ax.set_yscale("log")
        log_ratio_axis(ax.yaxis)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    for ax in axes[len(models):]:
        ax.set_visible(False)
    for ax in axes[::ncol]:
        ax.set_ylabel("revenue ÷ rental")
    for ax in axes[-ncol:]:
        ax.set_xlabel("utilization")
    handles = [plt.Line2D([], [], color=SERIES[(g, "base")][0], lw=2, label=SERIES[(g, "base")][1])
               for g in ("h100", "b200")]
    handles += [matplotlib.patches.Patch(color=MUTED, alpha=0.3,
                                         label=f"range over in:out ratios {', '.join(f'{r}:1' for r in cfg['io_ratio_sensitivity'])}"),
                plt.Line2D([], [], color=MUTED, lw=1, ls=":", label="max-throughput point (no latency floor)")]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8)
    fig.suptitle(f"Sensitivity — line = {r0}:1 in:out at ≥{cfg['interactivity_floor_tok_s_per_user']} tok/s/user; "
                 "band = in:out ratio range; black line = breakeven", x=0.01, ha="left",
                 fontweight="bold", fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_relative(s: pd.DataFrame, rental: pd.DataFrame, path: Path):
    """B200 ÷ H100: token-implied value vs rental price ratio."""
    base = s[s.case == "base"].pivot(index="model", columns="gpu", values="revenue")
    rel = (base["b200"] / base["h100"]).dropna()
    models = list(rel.index)
    fig, ax = plt.subplots(figsize=(8.5, 0.55 * len(models) + 1.8))
    y = np.arange(len(models))
    ax.hlines(y, 0, rel.values, color=GRID, lw=1, zorder=1)
    ax.scatter(rel.values, y, s=60, color=SERIES[("b200", "base")][0],
               edgecolor=SURFACE, linewidth=2, zorder=3, label="token-implied value ratio")
    for yy, v in zip(y, rel.values):
        ax.text(v, yy - 0.28, f"{v:.1f}×", ha="center", fontsize=8, color=INK2)
    rp = rental.pivot_table(index="series", columns="gpu", values="price_per_gpu_hour")
    styles = {"silicondata_index_faq": ("-", "Silicon Data index (FAQ)"),
              "silicondata_index_widget": ("--", "Silicon Data index (widget)"),
              "inferencex_retail": (":", "InferenceX retail assumption")}
    for ser, (ls, lab) in styles.items():
        if ser in rp.index:
            v = rp.loc[ser, "b200"] / rp.loc[ser, "h100"]
            ax.axvline(v, color=INK2, ls=ls, lw=1, label=f"rental ratio: {lab} = {v:.2f}×")
    ax.set_yticks(y, models)
    ax.invert_yaxis()
    ax.set_xlim(0, max(rel.max() * 1.15, 3))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("B200 ÷ H100")
    ax.set_title("B200 vs H100: what tokens say a GPU-hour is worth vs what it rents for",
                 loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return rel


def chart_timeseries(ts: pd.DataFrame, path: Path) -> bool:
    if ts.date.nunique() < 2:
        return False
    d = ts[ts.case == "base"]
    models = list(dict.fromkeys(d.model))
    fig, axes = plt.subplots(1, len(models), figsize=(2.4 * len(models), 2.8), sharey=True)
    for ax, m in zip(np.atleast_1d(axes), models):
        for gpu in ("h100", "b200"):
            g = d[(d.model == m) & (d.gpu == gpu)].sort_values("date")
            ax.plot(pd.to_datetime(g.date), g.spread_ratio, color=SERIES[(gpu, "base")][0],
                    lw=2, label=SERIES[(gpu, "base")][1])
        ax.axhline(1, color=INK, lw=1)
        ax.set_title(m, loc="left", fontsize=9)
        ax.xaxis.set_major_locator(matplotlib.dates.AutoDateLocator(minticks=2, maxticks=4))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %d"))
        ax.tick_params(axis="x", labelrotation=45, labelsize=7)
    np.atleast_1d(axes)[0].set_ylabel("revenue ÷ rental")
    np.atleast_1d(axes)[0].legend(fontsize=8)
    fig.suptitle("Spread ratio over time (base assumptions)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


# --- markdown helpers -------------------------------------------------------

def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.values) + " |")
    return "\n".join(lines)


def money(v, d=2):
    return "" if pd.isna(v) else f"${v:,.{d}f}"


def build():
    cfg = yaml.safe_load(open(ROOT / "assumptions.yaml"))
    s = pd.read_csv(OUT / "spread_summary.csv")
    sens = pd.read_csv(OUT / "sensitivity.csv")
    prov = pd.read_csv(OUT / "provider_spread.csv")
    ops = pd.read_csv(OUT / "operating_points.csv")
    rental = pd.read_csv(DATA / "gpu_rental.csv")
    prices = pd.read_csv(DATA / "api_prices.csv")
    ts_path = SNAP / "timeseries.csv"
    ts = pd.read_csv(ts_path) if ts_path.exists() else pd.DataFrame(columns=["date"])
    date = prices.retrieved_date.max()

    CHARTS.mkdir(exist_ok=True)
    chart_spread(s, CHARTS / "spread_by_model_gpu.png", cfg)
    chart_sensitivity(sens, CHARTS / "sensitivity.png", cfg)
    rel = chart_relative(s, rental, CHARTS / "b200_vs_h100.png")
    has_ts = chart_timeseries(ts, CHARTS / "timeseries.png")

    # summary table
    t = s.assign(
        GPU=s.gpu.str.upper() + " " + s.precision,
        **{"providers": s.n_providers,
           "blended $/Mtok (min–med–max)": s.apply(lambda r: f"{r.price_min:.2f}–{r.price_median:.2f}–{r.price_max:.2f}", axis=1),
           "tok/s/GPU": s.tput_per_gpu.round(0).astype("Int64"),
           "tok/s/GPU (max)": s.tput_per_gpu_max.round(0).astype("Int64"),
           "revenue $/h": s.revenue.map(money),
           "rental $/h": s.rental.map(money),
           "spread $/h": s.spread.map(money),
           "ratio": s.spread_ratio.map(lambda v: f"{v:.2f}×"),
           "breakeven util": s.breakeven_utilization.map(lambda v: f"{v:.0%}"),
           "bench date": s.bench_dates})
    t = t[["model", "GPU", "case", "providers", "blended $/Mtok (min–med–max)", "tok/s/GPU",
           "tok/s/GPU (max)", "revenue $/h", "rental $/h", "spread $/h", "ratio",
           "breakeven util", "bench date"]]

    # rental table
    rt = rental.assign(price=rental.price_per_gpu_hour.map(money))[
        ["gpu", "series", "price", "method", "estimate", "notes"]]

    # provider extremes
    pb = prov.sort_values("spread_ratio")
    lines_prov = []
    for (m, g), d in pb.groupby(["model", "gpu"], sort=False):
        lo, hi = d.iloc[0], d.iloc[-1]
        lines_prov.append({"model": m, "GPU": g.upper(),
                           "cheapest provider": f"{lo.provider} ({lo.quantization}) {lo.spread_ratio:.2f}×",
                           "most expensive": f"{hi.provider} ({hi.quantization}) {hi.spread_ratio:.2f}×",
                           "providers above breakeven": f"{(d.spread_ratio > 1).sum()}/{len(d)}"})
    prov_t = pd.DataFrame(lines_prov).sort_values(["model", "GPU"])

    # gaps
    gaps = []
    for m in cfg["models"]:
        for gpu in cfg["gpus"]:
            o = ops[(ops.model_key == m["key"]) & (ops.gpu == gpu) & (ops.op_point == "floor")
                    & (ops.precision == m["base_precision"][gpu])]
            have = {f"{int(a)}/{int(b)}" for a, b in zip(o.isl, o.osl)}
            miss = {"1024/1024", "8192/1024"} - have
            if miss:
                gaps.append(f"- **{m['key']} on {gpu.upper()} ({m['base_precision'][gpu]})**: no benchmark "
                            f"meeting the interactivity floor for {', '.join(sorted(miss))}; ratios use the "
                            "nearest measured sequence (estimate=true).")
            dates = sorted(set(o.bench_date))
            if dates and dates[-1] < (pd.Timestamp(date) - pd.Timedelta(days=180)).date().isoformat():
                gaps.append(f"- **{m['key']} on {gpu.upper()}**: newest benchmark is {dates[-1]} "
                            "(>6 months old; software has improved since, so throughput is likely understated).")
    unk = prices[prices.quantization == "unknown"].groupby("model_key").provider.count()
    rd = rental.pivot_table(index="gpu", columns="series", values="price_per_gpu_hour")

    worst = s[s.case == "base"].sort_values("spread_ratio").iloc[0]
    best = s.sort_values("spread_ratio").iloc[-1]
    rr_sd = rd.loc["b200", cfg["rental_base_series"]] / rd.loc["h100", cfg["rental_base_series"]]

    md = f"""# Token Spread — report {date}

*Generated by `report.py` from `outputs/` (data retrieved {date}). Re-run: see README.*

**Question.** What does a GPU-hour earn when it serves open-weight LLM tokens at market API
prices, compared with what that GPU-hour rents for — and does that tell us something rental
indices don't?

**Base assumptions** (`assumptions.yaml`): input:output = {cfg['io_ratio_base']}:1,
utilization = {cfg['utilization_base']:.0%}, throughput = best benchmark point with
≥ {cfg['interactivity_floor_tok_s_per_user']} tok/s per user, price = {cfg['price_statistic']}
OpenRouter provider, rental = `{cfg['rental_base_series']}`.

## Headlines

- Lowest base-case ratio: **{worst.model} on {worst.gpu.upper()}** at {worst.spread_ratio:.2f}×
  (breakeven utilization {worst.breakeven_utilization:.0%}).
- Highest ratio: **{best.model} on {best.gpu.upper()} {best.precision}** at {best.spread_ratio:.2f}×.
- B200 rents for {rr_sd:.2f}× an H100, but at the same precision the token-implied value of a B200-hour is
  {rel.min():.1f}×–{rel.max():.1f}× an H100-hour, depending on the model (chart 3).

## 1. Summary table

{md_table(t)}

`tok/s/GPU` = total (input+output) tokens/s per GPU at the base in:out ratio, interactivity-floor
point; `(max)` = highest throughput with no latency floor. Breakeven util = utilization at
which revenue = rental. Rows with `estimate=True` in `outputs/spread_summary.csv` use
interpolated throughput (see section 7).

![spread by model and GPU](charts/spread_by_model_gpu.png)

## 2. Sensitivity: utilization × input:output ratio

![sensitivity](charts/sensitivity.png)

Full grid (also with the max-throughput operating point): `outputs/sensitivity.csv`.

## 3. B200 vs H100 relative value

![b200 vs h100](charts/b200_vs_h100.png)

If rental markets priced GPUs by the tokens they produce, the dots would sit on the rental-ratio
lines. Dots to the right mean B200 is cheap relative to H100 for that model (or H100 is dear).

## 4. Provider dispersion (base case, one rental price, many API prices)

{md_table(prov_t)}

Full table: `outputs/provider_spread.csv`.

## 5. Rental prices used

{md_table(rt)}

{"## 6. Over time\n\n![time series](charts/timeseries.png)\n" if has_ts else "## 6. Over time\n\nOnly one snapshot so far; the time-series chart appears after the second daily run.\n"}
## 7. Data gaps and caveats

**Gaps found this run**

{chr(10).join(gaps) if gaps else "- none"}
- **No 8B-class model**: InferenceX doesn't benchmark one, so there is no comparable throughput.
- **Newest frontier open models** (DeepSeek-V4, Kimi-K3, GLM-5.2) have B200 but no H100 data
  on InferenceX, so they are left out of v0.
- Providers with **unknown quantization** on OpenRouter: {", ".join(f"{k} {v}" for k, v in unk.items()) or "none"}.
  They are included in the price statistics regardless of precision.

**Caveats**

- **Throughput dominates.** The interactivity floor alone moves results by up to several ×
  (compare `tok/s/GPU` with `(max)`). Benchmarks use random tokens and fixed lengths, with no
  prefix-cache hits, no traffic burstiness and no long-context tail.
- **3:1 and 10:1 ratios are not measured.** InferenceX measures 1k/1k (1:1) and 8k/1k (8:1).
  3:1 is log-interpolated and 10:1 is held at 8:1. The 1:1 and 8:1 points can come from
  different dates and software versions.
- **Configurations differ across GPUs.** The best point may use speculative decoding (MTP) on
  one GPU and not the other, and some points (e.g. DeepSeek-R1 on H100) need multi-node
  disaggregated serving. These are the best published configurations, not matched ones.
- **Prices are list prices.** OpenRouter shows public per-token prices only, without volume
  deals, batch discounts or cache-hit pricing. Precision is not matched per provider: the
  median is across all providers, and an fp4 provider counts the same as a bf16 one.
- **Rental is neocloud on-demand.** Silicon Data's public page shows two different readings
  (FAQ vs widget; both are recorded). Term contracts and hyperscalers price differently.
  InferenceX's owner-TCO figures (H100 {money(rd.loc['h100'].get('inferencex_owner_tco'))},
  B200 {money(rd.loc['b200'].get('inferencex_owner_tco'))}) are a floor for what serving
  costs an owner-operator.
- **Revenue ≠ margin.** The spread excludes networking, storage, CPU hosts, engineering,
  idle capacity reserved for peaks, and OpenRouter's fee.
"""
    (ROOT / "report.md").write_text(md)
    day = SNAP / str(date)
    if day.exists():
        shutil.copy2(ROOT / "report.md", day / "report.md")
    print(f"wrote report.md and {len(list(CHARTS.glob('*.png')))} charts")


if __name__ == "__main__":
    build()
