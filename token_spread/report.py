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


def chart_breakeven(be: pd.DataFrame, path: Path, cfg):
    """Tokens/s per GPU needed to cover rent (hollow) vs measured (filled, open-weight only)."""
    order = be[be.gpu == "b200"].sort_values("breakeven_tput_per_gpu").model.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.36 * len(order) + 1.9), sharey=True)
    for ax, gpu in zip(axes, ("h100", "b200")):
        color = SERIES[(gpu, "base")][0]
        d = be[be.gpu == gpu].set_index("model").reindex(order)
        y = np.arange(len(order))
        for yy, (m, r) in zip(y, d.iterrows()):
            if r.weights == "open" and np.isfinite(r.measured_tput_per_gpu):
                ax.plot([r.breakeven_tput_per_gpu, r.measured_tput_per_gpu], [yy, yy], color=GRID, lw=2, zorder=1)
                ax.scatter(r.measured_tput_per_gpu, yy, s=46, color=color, zorder=3, edgecolor=SURFACE, lw=1.5)
            ax.scatter(r.breakeven_tput_per_gpu, yy, s=46, facecolor=SURFACE, edgecolor=color, lw=1.8, zorder=4)
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.set_title(f"{gpu.upper()} · rent ${d.rental.dropna().iloc[0]:.2f}/h", loc="left")
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("tokens/s per GPU (log scale)")
    def label(m):
        r = be[be.model == m].iloc[0]
        if r.analysis != "price-only":
            return m
        return f"{m}  ({r.lab}{', open' if r.weights == 'open' else ''})"
    labels = [label(m) for m in order]
    axes[0].set_yticks(range(len(order)), labels)
    axes[0].invert_yaxis()
    handles = [plt.Line2D([], [], ls="", marker="o", mfc=SURFACE, mec=INK2, mew=1.8, label="needed to cover rent"),
               plt.Line2D([], [], ls="", marker="o", color=INK2, label="measured (benchmarked open-weight)")]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=8)
    fig.suptitle(f"Breakeven throughput at list price · {cfg['io_ratio_base']}:1 in:out · "
                 f"{cfg['utilization_base']:.0%} utilization", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_power_chain(chain: pd.DataFrame, path: Path, cfg, region_label: str):
    """Electricity -> owner cost -> rent -> token revenue, per GPU (log scale).
    Token revenue: median over base cases, whisker = min..max model."""
    steps = [("power_cost", "Electricity"), ("owner_tco", "Owner cost (TCO)"),
             ("rent", "Rent"), ("revenue", "Token revenue")]
    base = chain[chain.case == "base"]
    fig, ax = plt.subplots(figsize=(9, 4.0))
    gpus = [g for g in ("h100", "b200") if (base.gpu == g).any()]
    h = 0.36
    for gi, g in enumerate(gpus):
        d = base[base.gpu == g]
        color, name = SERIES[(g, "base")]
        y = np.arange(len(steps)) + (gi - (len(gpus) - 1) / 2) * h
        vals = [d[k].median() for k, _ in steps]
        ax.barh(y, vals, height=h - 0.05, color=color, label=name, zorder=2)
        lo, hi = d.revenue.min(), d.revenue.max()
        ax.errorbar([vals[-1]], [y[-1]], xerr=[[vals[-1] - lo], [hi - vals[-1]]], fmt="none",
                    ecolor=INK2, elinewidth=1, capsize=2.5, zorder=3)
        ends = vals[:-1] + [hi]
        for yy, v, e in zip(y, vals, ends):
            ax.text(e * 1.06, yy, f"${v:.2f}", va="center", fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:g}"))
    ax.set_yticks(range(len(steps)), [s for _, s in steps])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("US dollars per GPU-hour (log scale)")
    p = cfg["power"]
    ax.set_xlim(right=ax.get_xlim()[1] * 1.8)
    ax.set_title(f"From electricity to tokens · {region_label} at ${chain.price_usd_per_kwh.iloc[0]:.3f}/kWh, "
                 f"PUE {p['pue_base']}", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=8)
    fig.text(0.01, 0.01, "Token revenue: median model (bar) and range across models (whisker).",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


COST_PARTS = [("depreciation", "Hardware depreciation", "#52514e"), ("financing", "Financing", "#898781"),
              ("hosting", "Data-centre space", "#aeb8bf"), ("power", "Electricity", "#eda100"),
              ("ops", "Operations", "#c3c2b7")]


def chart_firm(econ: pd.DataFrame, path: Path):
    """Per GPU: stacked cost per GPU-hour vs revenue (rent x occupancy)."""
    b = econ[econ.base].set_index("gpu")
    gpus = list(b.index)
    fig, ax = plt.subplots(figsize=(9, 2.9))
    for i, g in enumerate(gpus):
        left = 0
        for k, lab, col in COST_PARTS:
            v = b.loc[g, k]
            ax.barh(i + 0.18, v, left=left, height=0.32, color=col, edgecolor=SURFACE, linewidth=1.5,
                    label=lab if i == 0 else None, zorder=2)
            left += v
        ax.text(left + 0.06, i + 0.18, f"cost \\${left:.2f}", va="center", fontsize=8, color=INK2)
        color = SERIES[(g, "base")][0]
        ax.barh(i - 0.18, b.loc[g, "revenue"], height=0.32, color=color, zorder=2)
        ax.text(b.loc[g, "revenue"] + 0.06, i - 0.18,
                f"revenue \\${b.loc[g, 'revenue']:.2f}  →  profit \\${b.loc[g, 'profit']:.2f} ({b.loc[g, 'net_margin']:.0%})",
                va="center", fontsize=8, color=INK2)
    ax.set_yticks(range(len(gpus)), [g.upper() for g in gpus])
    ax.invert_yaxis()
    ax.set_xlim(0, b.revenue.max() * 1.75)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("US dollars per GPU-hour (calendar hour, rented or idle)")
    occ = b.occupancy.iloc[0]
    ax.set_title(f"GPU rental firm: cost of owning a GPU vs rent collected ({occ:.0%} of hours rented)", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=5, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


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
    return "" if pd.isna(v) else ("−$" if v < 0 else "$") + f"{abs(v):,.{d}f}"


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
    be_path, pc_path = OUT / "breakeven_throughput.csv", OUT / "price_comparison.csv"
    closed_md = ""
    if be_path.exists() and pc_path.exists():
        be, pc = pd.read_csv(be_path), pd.read_csv(pc_path)
        chart_breakeven(be, CHARTS / "breakeven_throughput.png", cfg)
        po = be[be.analysis == "price-only"]
        cb = po.pivot_table(index=["model", "lab", "weights"], columns="gpu",
                                                     values="breakeven_tput_per_gpu").reset_index()
        cb = cb.merge(pc[["model", "blended_price"]], on="model")
        n_open = po.groupby("gpu").open_models_compared.max().to_dict()
        cnt = po.pivot_table(index="model", columns="gpu",
                                                      values="open_models_at_or_above").reset_index()
        cb = cb.merge(cnt, on="model", suffixes=("", "_n")).sort_values("blended_price", ascending=False)
        closed_t = pd.DataFrame({
            "model": cb.model, "lab": cb.lab, "weights": cb.weights,
            "blended $/Mtok": cb.blended_price.map(lambda v: f"${v:.2f}"),
            "needed tok/s per H100": cb.h100.map(lambda v: f"{v:,.0f}"),
            "needed tok/s per B200": cb.b200.map(lambda v: f"{v:,.0f}"),
            f"benchmarked models above (H100, of {n_open.get('h100', 0)})": cb.h100_n.astype(int),
            f"benchmarked models above (B200, of {n_open.get('b200', 0)})": cb.b200_n.astype(int)})
        pc_t = pd.DataFrame({
            "model": pc.model, "weights": pc.weights, "analysis": pc.analysis, "lab": pc.lab,
            "blended $/Mtok": pc.blended_price.map(lambda v: f"${v:.3f}"),
            "endpoint range": [f"${a:.3f}–${b:.3f}" for a, b in zip(pc.endpoint_blended_min, pc.endpoint_blended_max)],
            "basis": pc.price_basis})
        op_max = be[be.analysis == "spread"].groupby("gpu").measured_tput_per_gpu.min()
        hi = cb.iloc[0]
        lo = cb.iloc[-1]
        closed_md = f"""## 6. Price-only models: breakeven throughput and price comparison

Closed models (Claude, GPT, Grok) publish prices but not their hardware or throughput, and some
open-weight models have no comparable benchmark yet (only agentic traces, or no runs). No
spread is computed for them. Instead: how many tokens/s per GPU would a model need for its
**list price** to cover the GPU's rent at {cfg['utilization_base']:.0%} utilization?
`needed = rent ÷ (3600 × utilization × blended price / 1e6)`. For open-weight models this is
the same breakeven, and spread ratio = measured ÷ needed.

- **{hi.model}** at ${hi.blended_price:.2f}/Mtok needs only **{hi.h100:,.0f} tok/s per H100**.
  The slowest open-weight model measured here manages {op_max.get('h100', float('nan')):,.0f}.
- **{lo.model}** at ${lo.blended_price:.2f}/Mtok needs **{lo.h100:,.0f} tok/s per H100**
  ({lo.b200:,.0f} per B200). {int(lo.h100_n)} of {n_open.get('h100', 0)} benchmarked models {'reaches' if int(lo.h100_n) == 1 else 'reach'} that on H100.
- These are thresholds, not estimates of closed-model throughput or margin. Closed labs may
  run other hardware (TPUs, Trainium, own clusters), bill hidden reasoning tokens as output,
  and discount cached input heavily.

![breakeven throughput](charts/breakeven_throughput.png)

{md_table(closed_t)}

**Price comparison** (blended at {cfg['io_ratio_base']}:1; price-only = OpenRouter list price,
benchmarked open-weight = median provider):

{md_table(pc_t)}

"""

    power_md = ""
    pc_path, ch_path = OUT / "power_costs.csv", OUT / "power_chain.csv"
    if pc_path.exists() and ch_path.exists():
        pcosts, chain = pd.read_csv(pc_path), pd.read_csv(ch_path)
        chart_power_chain(chain, CHARTS / "power_chain.png", cfg,
                          pcosts[pcosts.region == cfg["power"]["base_region"]].label.iloc[0])
        pw = cfg["power"]
        pr = pcosts.pivot_table(index=["region", "label", "price_usd_per_kwh", "period"], columns="gpu",
                                values=["power_cost_per_gpu_hour", "power_share_of_rent"]).reset_index()
        pr = pr.sort_values("price_usd_per_kwh")
        region_t = pd.DataFrame({
            "region": pr["label"], "$/kWh": pr["price_usd_per_kwh"].map(lambda v: f"${v:.3f}"),
            "period": pr["period"],
            "H100 power $/h": pr[("power_cost_per_gpu_hour", "h100")].map(money),
            "B200 power $/h": pr[("power_cost_per_gpu_hour", "b200")].map(money),
            "share of H100 rent": pr[("power_share_of_rent", "h100")].map(lambda v: f"{v:.1%}"),
            "share of B200 rent": pr[("power_share_of_rent", "b200")].map(lambda v: f"{v:.1%}")})
        cb = chain[chain.case == "base"]
        chain_t = pd.DataFrame({
            "model": cb.model, "GPU": cb.gpu.str.upper() + " " + cb.precision,
            "power $/h": cb.power_cost.map(money), "owner TCO $/h": cb.owner_tco.map(money),
            "rent $/h": cb.rent.map(money), "revenue $/h": cb.revenue.map(money),
            "tokens per kWh": cb.tokens_per_kwh.map(lambda v: f"{v / 1e6:.2f}M"),
            "revenue per kWh": cb.revenue_per_kwh.map(money),
            "revenue ÷ power": cb.revenue_over_power.map(lambda v: f"{v:.0f}×"),
            "measured GPU W (% TDP)": [f"{w:.0f} ({p:.0%})" if pd.notna(w) else "–"
                                        for w, p in zip(cb.measured_gpu_w, cb.measured_pct_of_tdp)]})
        bpc = pcosts[pcosts.region == pw["base_region"]].set_index("gpu")
        power_md = f"""## 7. From electricity to tokens

A GPU-hour's cost starts with electricity. Each GPU draws its **all-in** power (chip plus its
share of host CPU, memory and network; SemiAnalysis: H100 {bpc.loc['h100', 'allin_kw']} kW,
B200 {bpc.loc['b200', 'allin_kw']} kW), and the facility adds cooling and conversion losses
(PUE {pw['pue_base']}). `power cost per GPU-hour = all-in kW × load factor ({pw['load_factor']}) × PUE × $/kWh`.

At the base region ({bpc.label.iloc[0]}, ${bpc.price_usd_per_kwh.iloc[0]:.3f}/kWh):

- Electricity costs **{money(bpc.loc['h100', 'power_cost_per_gpu_hour'])} per H100-hour** and
  **{money(bpc.loc['b200', 'power_cost_per_gpu_hour'])} per B200-hour**: {bpc.loc['h100', 'power_share_of_rent']:.1%}
  and {bpc.loc['b200', 'power_share_of_rent']:.1%} of the rent, and about
  {bpc.loc['h100', 'power_share_of_owner_tco']:.0%} / {bpc.loc['b200', 'power_share_of_owner_tco']:.0%} of the owner's full cost (SemiAnalysis TCO).
- Across regions ({money(pcosts.price_usd_per_kwh.min(), 3)}–{money(pcosts.price_usd_per_kwh.max(), 3)}/kWh),
  power is {pcosts.power_share_of_rent.min():.1%}–{pcosts.power_share_of_rent.max():.1%} of rent.
- Turned into tokens and sold at market prices, one kWh earns
  {money(cb.revenue_per_kwh.min())}–{money(cb.revenue_per_kwh.max())}: **{cb.revenue_over_power.min():.0f}–{cb.revenue_over_power.max():.0f}×**
  what the electricity cost.
- Measured GPU draw (newer InferenceX runs only) is {cb.measured_pct_of_tdp.min():.0%}–{cb.measured_pct_of_tdp.max():.0%} of
  TDP at the chosen operating points, so the full-load assumption is conservative.

![power chain](charts/power_chain.png)

{md_table(chain_t)}

**Electricity cost per GPU-hour by region** (EIA: latest month, by sector; Eurostat:
{pw['eurostat_band']} kWh/yr band, excl. VAT, converted at the ECB rate):

{md_table(region_t)}

"""

    firm_md = ""
    fe_path, vs_path, src_path = OUT / "firm_economics.csv", OUT / "value_split.csv", DATA / "rental_firm_sources.csv"
    if fe_path.exists() and vs_path.exists():
        econ, split, fsrc = pd.read_csv(fe_path), pd.read_csv(vs_path), pd.read_csv(src_path)
        chart_firm(econ, CHARTS / "firm_economics.png")
        b = econ[econ.base].set_index("gpu")
        f = cfg["rental_firm"]
        firm_t = pd.DataFrame({
            "per GPU-hour": ["Hardware depreciation", "Financing", "Data-centre space", "Electricity", "Operations",
                             "**Full cost**", f"Revenue (rent × {f['occupancy_base']:.0%})", "**Profit**",
                             "Margin before depreciation & interest (EBITDA)", "Operating margin", "Net margin",
                             "Occupancy needed to break even", "Payback on hardware (years)",
                             "SemiAnalysis owner cost (cross-check)"],
            **{g.upper(): [money(b.loc[g, "depreciation"]), money(b.loc[g, "financing"]), money(b.loc[g, "hosting"]),
                           money(b.loc[g, "power"]), money(b.loc[g, "ops"]), money(b.loc[g, "full_cost"]),
                           money(b.loc[g, "revenue"]), money(b.loc[g, "profit"]),
                           f"{b.loc[g, 'ebitda_margin']:.0%}", f"{b.loc[g, 'operating_margin']:.0%}",
                           f"{b.loc[g, 'net_margin']:.0%}", f"{b.loc[g, 'breakeven_occupancy']:.0%}",
                           f"{b.loc[g, 'payback_years']:.1f}", money(b.loc[g, "semianalysis_owner_tco"])]
               for g in b.index}})
        occ_t = econ[econ.depreciation_years == f["depreciation_years"]].pivot_table(
            index="occupancy", columns="gpu", values="profit").reset_index()
        occ_t = pd.DataFrame({"occupancy": occ_t.occupancy.map(lambda v: f"{v:.0%}"),
                              **{f"{g.upper()} profit $/h": occ_t[g].map(money) for g in b.index}})
        vs = split.assign(GPU=split.gpu.str.upper())
        split_t = pd.DataFrame({
            "model": vs.model, "GPU": vs.GPU,
            "landlord costs $/h": (vs.power_cost + vs.hosting_cost + vs.ops_cost + vs.depreciation_cost + vs.financing_cost).map(money),
            "landlord profit $/h": vs.landlord_profit.map(money), "rent $/h": vs.rent.map(money),
            "token revenue $/h": vs.token_revenue.map(money), "inference provider profit $/h": vs.provider_profit.map(money),
            "own-and-serve profit $/h": vs.integrated_profit.map(money),
            "full cost per M tokens": vs.full_cost_per_mtok.map(lambda v: f"${v:.3f}"),
            "price per M tokens": vs.price_per_mtok.map(lambda v: f"${v:.3f}")})
        cw = fsrc.set_index("item")["value"]
        src_t = fsrc[fsrc.used_in_model].assign(source=lambda d: d.source_url.map(lambda u: f"[link]({u})"))[
            ["item", "gpu", "value", "unit", "low", "high", "estimate", "source"]]
        hw_share = {g: (b.loc[g, "depreciation"] + b.loc[g, "financing"]) / b.loc[g, "full_cost"] for g in b.index}
        firm_md = f"""## 8. Who makes the money: the GPU rental firm

Electricity is not most of a GPU rental firm's cost. Owning a GPU for one hour costs:
`hardware (depreciation + financing) + data-centre space + electricity + operations`.
Hardware and its financing are {min(hw_share.values()):.0%}–{max(hw_share.values()):.0%} of the total.
The firm collects rent only for the share of hours a customer is using the GPU (occupancy,
{f['occupancy_base']:.0%} here).

![firm economics](charts/firm_economics.png)

{md_table(firm_t)}

Assumptions (`assumptions.yaml` → `rental_firm`): capex per GPU = 8-GPU server ÷ 8, straight-line
over {f['depreciation_years']} years, financed at {f['cost_of_capital']:.0%} (annuity), colocation
${f['colocation_usd_per_kw_month']}/kW-month on all-in kW, operations ${f['ops_usd_per_gpu_hour']:.2f}/GPU-hour.

**Profit by occupancy** ({f['depreciation_years']}-year depreciation):

{md_table(occ_t)}

**Reality check: CoreWeave, Q2 2026.** Revenue ${cw['coreweave_q2_2026_revenue']:,.0f}M; adjusted EBITDA
margin {cw['coreweave_q2_2026_adj_ebitda_margin']:.0%}; depreciation {cw['coreweave_q2_2026_depreciation'] / cw['coreweave_q2_2026_revenue']:.0%}
and interest {cw['coreweave_q2_2026_interest'] / cw['coreweave_q2_2026_revenue']:.0%} of revenue; operating margin
{cw['coreweave_q2_2026_operating_margin']:.0%}. The model's EBITDA margins are in the same range, but its
operating margins are far higher. A fast-growing firm pays depreciation and interest on capacity
before it earns revenue, sells mostly on multi-year contracts below on-demand prices, and carries
overheads (sales, R&D, stock compensation) that this per-GPU model leaves out.

**Where one rented GPU-hour of token revenue goes** (base cases): the GPU landlord's costs and
profit add up to the rent; the inference provider keeps token revenue minus rent (the token
spread). An operator that owns its GPUs and sells tokens keeps token revenue minus full cost.

{md_table(split_t)}

**Sources used in the firm model:**

{md_table(src_t)}

"""

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
            if gpu not in m["base_precision"]:
                gaps.append(f"- **{m['key']} on {gpu.upper()}**: no InferenceX benchmark on this GPU; "
                            "the model appears on the other GPU only.")
                continue
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
        # base precision vs what providers report serving
        for gpu, prec in m["base_precision"].items():
            q = prices[(prices.model_key == m["key"]) & (prices.quantization != "unknown")].quantization
            if len(q) and q.mode().iloc[0] != prec and (q == prec).sum() < len(q) / 2:
                gaps.append(f"- **{m['key']} on {gpu.upper()}**: benchmarked at {prec}, but most providers "
                            f"report serving {q.mode().iloc[0]}.")
    base_ops = ops[(ops.op_point == "floor") & ops.apply(
        lambda r: any(m["key"] == r.model_key and m["base_precision"].get(r.gpu) == r.precision
                      for m in cfg["models"]), axis=1) & (ops.isl >= ops.osl)]
    if "sweep_edge" in base_ops and len(base_ops):
        n_edge = int(base_ops.sweep_edge.sum())
        gaps.append(f"- **Sweep edges:** {n_edge} of {len(base_ops)} chosen benchmark points are the last point "
                    "of their concurrency sweep and still well above the speed floor. The benchmark stopped "
                    "before reaching the floor, so throughput there is a lower bound.")
    for m in cfg.get("price_only_open_models", []):
        gaps.append(f"- **{m['key']}** (open-weight): {m['reason']}; shown as price-only.")
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
interpolated throughput (see section 10).

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

{closed_md}{power_md}{firm_md}{"## 9. Over time\n\n![time series](charts/timeseries.png)\n" if has_ts else "## 9. Over time\n\nOnly one snapshot so far; the time-series chart appears after the second daily run.\n"}
## 10. Data gaps and caveats

**Gaps found this run**

{chr(10).join(gaps) if gaps else "- none"}
- **No 8B-class model**: InferenceX doesn't benchmark one, so there is no comparable throughput.
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
- **Electricity is modelled, not metered.** Power cost uses SemiAnalysis all-in kW per GPU at
  full load, an assumed PUE and average published tariffs. Large operators buy power through
  contracts (PPAs) whose prices are not public, and pay demand charges not captured here.
- **The rental-firm model is generic.** Server prices are vendor estimates (NVIDIA publishes no
  list price), depreciation life and financing cost vary by firm, and real fleets mix contract
  and on-demand prices. It leaves out sales, R&D and corporate overheads.
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
