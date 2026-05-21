from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .metrics import RunMetrics, aggregate_runs


PALETTE = {
    "exhaustive_pair_search": "#2ca02c",
    "traditional_greedy": "#ff7f0e",
    "decoupled_ai": "#1f77b4",
    "jo_vppm": "#d62728",
}


def algorithm_label(name: str) -> str:
    return {
        "exhaustive_pair_search": "Exhaustive Pair-Search",
        "traditional_greedy": "Traditional Greedy",
        "decoupled_ai": "Decoupled AI",
        "jo_vppm": "JO-VPPM",
    }.get(name, name)


def plot_dashboard(path: Path, grouped_runs: Dict[str, List[RunMetrics]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    algorithms = [name for name, runs in grouped_runs.items() if runs]
    aggregates = [aggregate_runs(grouped_runs[name]) for name in algorithms]
    labels = [algorithm_label(name) for name in algorithms]
    colors = [PALETTE.get(name, "#888888") for name in algorithms]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("JO-VPPM Algorithm Benchmark", fontsize=15, fontweight="bold")

    _bar(axes[0, 0], labels, [a["acceptance_rate_mean"] for a in aggregates], colors, "Acceptance Rate (%)")
    _bar(axes[0, 1], labels, [a["msd_violation_rate_mean"] for a in aggregates], colors, "MSD Violation Rate (%)")
    _bar(axes[0, 2], labels, [a["sla_violation_rate_mean"] for a in aggregates], colors, "SLA Violation Rate (%)")
    _bar(axes[1, 0], labels, [a["avg_latency_ms_mean"] for a in aggregates], colors, "Average Latency (ms)")
    _bar(axes[1, 1], labels, [a["avg_queue_latency_ms_mean"] for a in aggregates], colors, "M/G/1 Queue Latency (ms)")
    _bar(axes[1, 2], labels, [a["avg_reward_mean"] for a in aggregates], colors, "Average Reward")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path / "dashboard.png", dpi=200, bbox_inches="tight")
    fig.savefig(path / "dashboard.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_latency_cdf(path: Path, grouped_runs: Dict[str, List[RunMetrics]]) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for algorithm, runs in grouped_runs.items():
        latencies = []
        for run in runs:
            latencies.extend(run.latencies_ms)
        if not latencies:
            continue
        ordered = np.sort(latencies)
        cdf = np.arange(1, len(ordered) + 1) / len(ordered)
        ax.plot(ordered, cdf, label=algorithm_label(algorithm), color=PALETTE.get(algorithm, "#888888"), lw=2)
    for threshold, label in [(10, "URLLC 10ms"), (30, "Video 30ms"), (50, "VoIP 50ms"), (100, "Data 100ms")]:
        ax.axvline(threshold, color="gray", linestyle="--", alpha=0.35, lw=1)
        ax.text(threshold + 0.3, 0.05, label, rotation=90, fontsize=8, color="gray")
    ax.set_xlabel("Accepted-request latency (ms)")
    ax.set_ylabel("CDF")
    ax.set_title("Latency CDF")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.savefig(path / "latency_cdf.png", dpi=200, bbox_inches="tight")
    fig.savefig(path / "latency_cdf.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_rolling_acceptance(path: Path, grouped_runs: Dict[str, List[RunMetrics]], window: int = 500) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for algorithm, runs in grouped_runs.items():
        curves = [run.rolling_acceptance(window) for run in runs]
        curves = [curve for curve in curves if len(curve)]
        if not curves:
            continue
        min_len = min(len(curve) for curve in curves)
        stack = np.array([curve[:min_len] for curve in curves])
        mean = stack.mean(axis=0)
        std = stack.std(axis=0)
        ci = 1.96 * std / max(1.0, np.sqrt(len(curves)))
        color = PALETTE.get(algorithm, "#888888")
        ax.plot(mean, label=algorithm_label(algorithm), color=color, lw=2)
        ax.fill_between(range(min_len), mean - ci, mean + ci, color=color, alpha=0.12)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Step")
    ax.set_ylabel("Acceptance Rate (%)")
    ax.set_title(f"Rolling Acceptance, window={window}")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.savefig(path / "rolling_acceptance_ci.png", dpi=200, bbox_inches="tight")
    fig.savefig(path / "rolling_acceptance_ci.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)


def _bar(ax, labels, values, colors, title):
    bars = ax.bar(labels, values, color=colors, alpha=0.85)
    ax.bar_label(bars, fmt="%.1f", fontsize=8, padding=3)
    ax.set_title(title)
    ax.tick_params(axis="x", labelrotation=20, labelsize=8)
    ax.grid(axis="y", alpha=0.2)
