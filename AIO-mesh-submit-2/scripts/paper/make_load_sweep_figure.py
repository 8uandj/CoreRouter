"""Regenerate the offered-intensity figure from the archived per-seed export."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2] / "docs/AIO-mesh-rev1"
POLICIES = [
    ("traditional_greedy_protected", "Greedy", "#457B9D", "o"),
    ("decoupled_ai_protected", "DAI", "#7B2CBF", "D"),
    ("saf_h_protected", "SAF-H", "#404040", "s"),
    ("harp_protected", "HARP", "#2A7D57", "^"),
]


def main():
    with (ROOT / "evidence/model_refresh_20261120/load_chain_per_seed.csv").open() as stream:
        rows = [r for r in csv.DictReader(stream) if int(r["initial_active_chains"]) == 0]
    cells = {}
    for row in rows:
        key = row["topology"], float(row["load_multiplier"]), row["algorithm"]
        samples = cells.setdefault(key, {})
        seed = int(row["seed"])
        if seed in samples:
            raise ValueError(f"Duplicate seed {seed} in {key}")
        samples[seed] = float(row["safe_acceptance_rate"])
    levels = sorted({load for _, load, _ in cells})
    rng = np.random.default_rng(20261119)
    fig, axes = plt.subplots(3, 2, figsize=(8.2, 7.1), sharex=True,
                             layout="constrained")
    for topo, title, (left, right) in zip(
        ["vietnam", "nsfnet", "geant2"], ["Vietnam", "NSFNET", "GEANT2"], axes
    ):
        for key, name, color, marker in POLICIES:
            means, differences, intervals = [], [], []
            for level in levels:
                group = cells[topo, level, key]
                reference = cells[topo, level, "saf_h_protected"]
                if len(group) != 20 or group.keys() != reference.keys():
                    raise ValueError(f"Incomplete or unpaired group: {topo} {level} {key}")
                delta = np.array([group[seed] - reference[seed] for seed in sorted(group)])
                differences.append(delta.mean())
                intervals.append(np.quantile(rng.choice(delta, (10_000, len(delta)))
                                             .mean(axis=1), [.025, .975]))
                means.append(np.mean(list(group.values())))
            left.plot(levels, means, color=color, marker=marker, label=name, markersize=4)
            if name == "SAF-H":
                right.axhline(0, color=color, linestyle="--", linewidth=1, label=name)
            else:
                right.plot(levels, differences, color=color, marker=marker, markersize=4)
                low, high = np.array(intervals).T
                right.fill_between(levels, low, high, color=color, alpha=.2)
        left.set_title(f"{title}: protected policies")
        left.set_ylabel("Safe acceptance (%)")
        right.set_title(f"{title}: contrast with SAF-H")
        right.set_ylabel("Difference (percentage points)")
        for ax in (left, right):
            ax.set_xticks(levels)
            ax.grid(axis="y", alpha=.25)
    for ax in axes[-1]:
        ax.set_xlabel("Offered-intensity multiplier")
    axes[0, 0].legend(ncol=2, frameon=False, loc="lower left", fontsize=8)
    fig.savefig(ROOT / "figs/load_sweep_three_topologies.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
