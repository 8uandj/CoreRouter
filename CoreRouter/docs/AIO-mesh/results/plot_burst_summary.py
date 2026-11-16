from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


METRICS = [
    "Acceptance Rate (%)",
    "MSD Violation Rate (%)",
    "SLA Violation Rate (%)",
    "Average Latency (ms)",
    "M/G/1 Queue Latency (ms)",
    "Average Reward",
]

ALGORITHMS = ["Traditional Greedy", "Decoupled AI", "HARP"]

PALETTE = {
    "Traditional Greedy": "#ff7f0e",
    "Decoupled AI": "#1f77b4",
    "HARP": "#d62728",
    "JO-VPPM": "#d62728",
}

TOPOLOGY_OUTPUT = {
    "VN": "VN_burst.pdf",
    "GEANT2": "Geant2_burst.pdf",
}


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_algorithm(name: str) -> str:
    return "HARP" if name.strip() == "JO-VPPM" else name.strip()


def rows_for_topology(rows: list[dict[str, str]], topology: str) -> list[dict[str, str]]:
    wanted = topology.upper()
    filtered = [row for row in rows if row["Topology"].upper() == wanted]
    by_algorithm = {normalize_algorithm(row["Algorithm"]): row for row in filtered}
    return [by_algorithm[name] for name in ALGORITHMS if name in by_algorithm]


def add_bar_chart(ax, labels: list[str], values: list[float], colors: list[str], title: str) -> None:
    bars = ax.bar(labels, values, color=colors, alpha=0.85)
    ax.bar_label(bars, fmt="%.1f", fontsize=10, padding=3)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.tick_params(axis="x", labelrotation=18, labelsize=10)
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)

    low = min(values)
    high = max(values)
    if low < 0 < high:
        margin = max((high - low) * 0.14, 1.0)
        ax.set_ylim(low - margin, high + margin)
    elif high > 0:
        ax.set_ylim(0, high * 1.22 + 0.1)
    else:
        ax.set_ylim(low * 1.22 - 0.1, 0)


def plot_topology(rows: list[dict[str, str]], topology: str, output_path: Path) -> None:
    topology_rows = rows_for_topology(rows, topology)
    if not topology_rows:
        raise ValueError(f"No rows found for topology {topology}")

    labels = [normalize_algorithm(row["Algorithm"]) for row in topology_rows]
    colors = [PALETTE.get(label, "#888888") for label in labels]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    for ax, metric in zip(axes.ravel(), METRICS):
        values = [float(row[metric]) for row in topology_rows]
        add_bar_chart(ax, labels, values, colors, metric)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot burst benchmark dashboards from burst_summary.csv.")
    parser.add_argument("--csv", type=Path, default=Path(__file__).with_name("burst_summary.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()

    rows = load_rows(args.csv)
    for topology, filename in TOPOLOGY_OUTPUT.items():
        plot_topology(rows, topology, args.output_dir / filename)


if __name__ == "__main__":
    main()
