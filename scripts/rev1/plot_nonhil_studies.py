#!/usr/bin/env python3
"""Plot the serialized policy-cost and SAF-H topology-size study."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cost", type=Path, required=True)
    parser.add_argument("--scale", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cost = json.loads(args.cost.read_text(encoding="utf-8"))
    scale = json.loads(args.scale.read_text(encoding="utf-8"))
    rows = cost["per_seed"]
    policies = ("harp", "saf_h")
    labels = ("HARP", "SAF-H")
    p50 = [np.mean([row[name]["decision_latency_p50_ms"] for row in rows]) for name in policies]
    p95 = [np.mean([row[name]["decision_latency_p95_ms"] for row in rows]) for name in policies]

    fig, axes = plt.subplots(1, 2, figsize=(7.15, 3.15))
    ax = axes[0]
    positions = np.arange(len(labels))
    ax.bar(positions - .18, p50, width=.36, color="#176B87", label="Per-seed P50")
    ax.bar(positions + .18, p95, width=.36, color="#B34A36", label="Per-seed P95")
    ax.set_xticks(positions, labels)
    ax.set_title("Vietnam (10 nodes)")
    ax.set_ylabel("Decision latency (ms; log scale)")
    ax.set_yscale("log")
    ax.grid(True, which="both", axis="y", alpha=.25)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    scale_rows = scale["measurements"]
    positions = [row["nodes"] for row in scale_rows]
    medians = [row["feasible_set_p50_ms_mean"] for row in scale_rows]
    tails = [row["feasible_set_p95_ms_mean"] for row in scale_rows]
    ax.plot(positions, medians, "o-", color="#176B87", linewidth=1.7, markersize=5, label="Feasible-set p50")
    ax.plot(positions, tails, "s--", color="#B34A36", linewidth=1.7, markersize=5, label="Feasible-set p95")
    ax.plot(positions, [row["decision_p95_ms_mean"] for row in scale_rows], "^-.", color="#3F7653", label="Decision P95")
    ax.set_xticks(positions)
    ax.set_xlabel("Grid size (nodes)")
    ax.set_title("SAF-H on synthetic grids")
    ax.set_yscale("log")
    ax.grid(True, which="both", axis="y", alpha=.25)
    ax.legend(frameon=False, fontsize=8)

    fig.tight_layout(w_pad=1.4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
