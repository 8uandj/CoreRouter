#!/usr/bin/env python3
"""
plot_pareto_design_space.py
────────────────────────────
Generates: "Figure 5 – Integrated Architectural Design Space & Pareto Sensitivity Curves"

Layout: 2 rows (NSFNET / GEANT2) × 3 cols (trade-off scenarios)

Trade-off 1 – SLA Quality   : X = Safe Acceptance (%), Y = SLA Violation Rate (%) [SLA Sweep]
Trade-off 2 – Routing Quality: X = Safe Acceptance (%), Y = Average Latency (ms)    [SLA Sweep]
Trade-off 3 – Action Stability: X = Safe Acceptance (%), Y = Switching Rate (%)     [Migration Sweep]

Plots curves for each variant by connecting the parameter sweep points.
High-contrast and bold styling for HARP Full (the absolute outer envelope / Pareto frontier).
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE     = Path("/home/hung8uandj/CoreRouter")
RES      = BASE / "results/benchmark_algorithm/load_sweep"  # default output folder
FIGS_DIR = BASE / "docs/AIO-mesh/Figs"
FIGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Variant catalogue ─────────────────────────────────────────────────────────
VARIANTS = {
    "HARP full": dict(
        short="HARP★", color="#c0392b", marker="*", ms=150, lw=2.5, ls="-", zo=20, bold=True),
    "HARP w/o adaptive penalty": dict(
        short="NoAdapt", color="#e67e22", marker="^", ms=80, lw=1.2, ls="--", zo=12, bold=False),
    "HARP w/o GAT": dict(
        short="w/o GAT", color="#2980b9", marker="s", ms=85, lw=1.2, ls="--", zo=12, bold=False),
    "HARP w/o hard masking": dict(
        short="NoMask", color="#27ae60", marker="D", ms=80, lw=1.0, ls=":", zo=10, bold=False),
    "HARP w/o mask + unchecked admission": dict(
        short="NoMask+U", color="#8e44ad", marker="v", ms=80, lw=1.0, ls=":", zo=8, bold=False),
    "HARP with soft MSD penalty": dict(
        short="SoftMSD", color="#616a6b", marker="P", ms=80, lw=1.0, ls=":", zo=8, bold=False),
}

TOPO_LABEL = {
    "nsfnet": r"$\bf{NSFNET}$" + "\n(14 nodes, N²=196)",
    "geant2": r"$\bf{GEANT2}$" + "\n(23 nodes, N²=529)",
}

# ── Style ─────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9.5,
    "axes.titlesize": 11.0,
    "axes.labelsize": 9.5,
    "svg.fonttype": "none",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})


def load_master_summary(topo: str) -> pd.DataFrame:
    path = RES / f"{topo}_master_ablation_parameter_sweep_5seeds.csv"
    if not path.exists():
        # Fallback to worker directory if running in Kaggle workspace
        fallback_path = Path("/kaggle/working/harp_ablation") / f"worker_{topo}" / f"{topo}_master_ablation_parameter_sweep_5seeds.csv"
        if fallback_path.exists():
            return pd.read_csv(fallback_path)
        raise FileNotFoundError(f"Cannot find master parameter sweep CSV for {topo} under {path} or {fallback_path}")
    return pd.read_csv(path)


def plot_integrated_pareto():
    topos = ["nsfnet", "geant2"]
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5),
                             gridspec_kw={"hspace": 0.40, "wspace": 0.26})
    
    for row_idx, topo in enumerate(topos):
        try:
            df = load_master_summary(topo)
        except FileNotFoundError as e:
            print(f"⚠️ Skipping {topo} plot: {e}")
            continue

        # 1. Plot Trade-off ①: SLA Quality vs. Acceptance (SLA sweep)
        ax_sla = axes[row_idx, 0]
        df_sla = df[df["param_type"] == "sla"].copy()
        
        # Remove 'None' to get a clean numeric parameter sweep curve, but keep it for marker check
        df_sla_num = df_sla[df_sla["param_val"] != "None"].copy()
        df_sla_num["param_val"] = df_sla_num["param_val"].astype(float)
        
        for vname, st in VARIANTS.items():
            vdf = df_sla_num[df_sla_num["variant"] == vname].sort_values("param_val")
            if vdf.empty:
                continue
            
            xs = vdf["safe_acceptance_rate_mean"].values
            ys = vdf["sla_violation_rate_mean"].values
            xerr = vdf["safe_acceptance_rate_std"].values
            yerr = vdf["sla_violation_rate_std"].values

            # Draw error bands/shading for standard deviation
            ax_sla.fill_between(xs, ys - yerr, ys + yerr, color=st["color"], alpha=0.08)

            # Draw the curve
            ax_sla.plot(xs, ys, color=st["color"], linestyle=st["ls"], linewidth=st["lw"],
                         label=st["short"], zorder=st["zo"])
            
            # Plot parameter points
            ax_sla.scatter(xs, ys, color=st["color"], marker=st["marker"], s=st["ms"] * 0.7,
                           edgecolors="black", linewidths=0.5, zorder=st["zo"] + 1)
            
            # Highlight default configuration (usually SLA = 1.5ms or None)
            vdf_default = df_sla[(df_sla["variant"] == vname) & (df_sla["param_val"] == "None")]
            if not vdf_default.empty:
                x_def = vdf_default["safe_acceptance_rate_mean"].values[0]
                y_def = vdf_default["sla_violation_rate_mean"].values[0]
                ax_sla.scatter(x_def, y_def, color=st["color"], marker=st["marker"], s=st["ms"] * 1.8,
                               edgecolors="black", linewidths=1.2, zorder=st["zo"] + 2)

        # 2. Plot Trade-off ②: Routing Quality vs. Acceptance (SLA sweep)
        ax_lat = axes[row_idx, 1]
        for vname, st in VARIANTS.items():
            vdf = df_sla_num[df_sla_num["variant"] == vname].sort_values("param_val")
            if vdf.empty:
                continue
            xs = vdf["safe_acceptance_rate_mean"].values
            ys = vdf["avg_latency_ms_mean"].values
            xerr = vdf["safe_acceptance_rate_std"].values
            yerr = vdf["avg_latency_ms_std"].values

            ax_lat.fill_between(xs, ys - yerr, ys + yerr, color=st["color"], alpha=0.08)
            ax_lat.plot(xs, ys, color=st["color"], linestyle=st["ls"], linewidth=st["lw"],
                         label=st["short"], zorder=st["zo"])
            ax_lat.scatter(xs, ys, color=st["color"], marker=st["marker"], s=st["ms"] * 0.7,
                           edgecolors="black", linewidths=0.5, zorder=st["zo"] + 1)
            
            vdf_default = df_sla[(df_sla["variant"] == vname) & (df_sla["param_val"] == "None")]
            if not vdf_default.empty:
                x_def = vdf_default["safe_acceptance_rate_mean"].values[0]
                y_def = vdf_default["avg_latency_ms_mean"].values[0]
                ax_lat.scatter(x_def, y_def, color=st["color"], marker=st["marker"], s=st["ms"] * 1.8,
                               edgecolors="black", linewidths=1.2, zorder=st["zo"] + 2)

        # 3. Plot Trade-off ③: Action Stability vs. Acceptance (Migration Sweep)
        ax_mig = axes[row_idx, 2]
        df_mig = df[df["param_type"] == "migration"].copy()
        df_mig["param_val"] = df_mig["param_val"].astype(float)
        
        for vname, st in VARIANTS.items():
            vdf = df_mig[df_mig["variant"] == vname].sort_values("param_val")
            if vdf.empty:
                continue
            xs = vdf["safe_acceptance_rate_mean"].values
            ys = vdf["switching_rate_mean"].values
            xerr = vdf["safe_acceptance_rate_std"].values
            yerr = vdf["switching_rate_std"].values

            ax_mig.fill_between(xs, ys - yerr, ys + yerr, color=st["color"], alpha=0.08)
            ax_mig.plot(xs, ys, color=st["color"], linestyle=st["ls"], linewidth=st["lw"],
                         label=st["short"], zorder=st["zo"])
            ax_mig.scatter(xs, ys, color=st["color"], marker=st["marker"], s=st["ms"] * 0.7,
                           edgecolors="black", linewidths=0.5, zorder=st["zo"] + 1)
            
            # Highlight default config (alert threshold = 0.80)
            vdf_default = vdf[vdf["param_val"] == 0.80]
            if not vdf_default.empty:
                x_def = vdf_default["safe_acceptance_rate_mean"].values[0]
                y_def = vdf_default["switching_rate_mean"].values[0]
                ax_mig.scatter(x_def, y_def, color=st["color"], marker=st["marker"], s=st["ms"] * 1.8,
                               edgecolors="black", linewidths=1.2, zorder=st["zo"] + 2)

        # Labels, Styling and ideal arrows
        for col_idx, ax in enumerate([ax_sla, ax_lat, ax_mig]):
            ax.grid(True, linestyle=":", alpha=0.45, linewidth=0.7)
            ax.set_axisbelow(True)
            ax.set_xlabel("Safe Acceptance Rate (%)", fontsize=9.5)
            
            # Ideal corners annotations
            ax.annotate("Ideal →", xy=(0.97, 0.03), xycoords="axes fraction",
                        fontsize=7.0, ha="right", va="bottom", color="#666666", style="italic")
            ax.annotate("↑ Ideal", xy=(0.03, 0.97), xycoords="axes fraction",
                        fontsize=7.0, ha="left", va="top", color="#666666", style="italic", rotation=90)
            
            # Add topology name to y-axis of column 0
            if col_idx == 0:
                ylab = "SLA Violation Rate (%)"
                ax.set_ylabel(f"{TOPO_LABEL[topo]}\n{ylab}", fontsize=10.0, fontweight="bold", labelpad=6)
            elif col_idx == 1:
                ax.set_ylabel("Average Latency (ms)", fontsize=9.5)
            elif col_idx == 2:
                ax.set_ylabel("Switching Rate (%)", fontsize=9.5)

            # Titles on first row
            if row_idx == 0:
                if col_idx == 0:
                    ax.set_title("① SLA Quality vs. Acceptance\n(SLA Latency Sweeps)", fontweight="bold", pad=10)
                elif col_idx == 1:
                    ax.set_title("② Routing Quality vs. Acceptance\n(SLA Latency Sweeps)", fontweight="bold", pad=10)
                elif col_idx == 2:
                    ax.set_title("③ Action Stability vs. Acceptance\n(Evacuation CPU Warning Sweeps)", fontweight="bold", pad=10)

    # ── Shared Legend ─────────────────────────────────────────────────────────
    legend_els = []
    for vn, st in VARIANTS.items():
        legend_els.append(Line2D([0], [0], color=st["color"], linestyle=st["ls"], linewidth=st["lw"],
                                 marker=st["marker"], markersize=7, markeredgecolor="black", label=st["short"]))
    
    legend_els.append(Line2D([0], [0], marker="o", color="none", markerfacecolor="black", markersize=10, 
                             markeredgecolor="black", label="Default Operating Point"))
    legend_els.append(mpatches.Patch(color="#aaaaaa", alpha=0.15, label="Cross-seed Std. Dev."))

    fig.legend(handles=legend_els, loc="lower center", ncol=5,
               fontsize=9.5, frameon=True, framealpha=0.98,
               edgecolor="#cccccc", bbox_to_anchor=(0.5, 0.01),
               title="Design Variants & Operational Sensitivity Sweeps  (lines = sensitivity curves;  larger markers = default configs)",
               title_fontsize=9.0)

    fig.suptitle(
        "Architectural Design Space & Pareto Sensitivity Curves: NSFNET and GEANT2\n"
        r"(X = Safe Acceptance Rate $\uparrow$;  Y = Cost metrics $\downarrow$;  "
        r"$\bigstar$ = HARP Full establishes the outer Pareto frontier envelope)",
        fontsize=12.0, fontweight="bold", y=0.99)

    fig.subplots_adjust(bottom=0.15, top=0.90)

    # Save outputs
    for fmt in ("pdf", "png", "svg"):
        out = FIGS_DIR / f"pareto_design_space.{fmt}"
        kw  = {"dpi": 200, "bbox_inches": "tight"} if fmt != "svg" else {"bbox_inches": "tight"}
        plt.savefig(out, **kw)
        print(f"✓ {fmt.upper():3s} → {out}")
    plt.close()


if __name__ == "__main__":
    plot_integrated_pareto()
