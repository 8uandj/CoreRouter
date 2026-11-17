"""Recompute historical seed summaries without training or modifying raw evidence.

This audits CSV arithmetic/coverage, not model lineage or matched request traces.
"""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev, stdev


SEEDS = (42, 100, 2024, 8888, 9999)
ABLATION_METRICS = (
    "acceptance_rate", "safe_acceptance_rate", "attempted_msd_violation_rate",
    "admitted_msd_violation_rate", "sla_violation_rate", "avg_latency_ms",
    "avg_reward",
)
BENCHMARK_METRICS = (
    "acceptance_rate", "msd_violation_rate", "sla_violation_rate",
    "avg_latency_ms", "avg_queue_latency_ms", "avg_reward",
)


def summarize_rows(rows, group_columns, metrics, expected_seeds, ddof):
    """Reject incomplete/invalid groups and return numeric mean/SD seed summaries."""
    if not rows:
        raise ValueError("empty result set")
    if ddof not in (0, 1):
        raise ValueError("ddof must be 0 or 1")
    expected = set(map(int, expected_seeds))
    if not expected or len(expected) <= ddof:
        raise ValueError("insufficient expected seeds")
    groups = defaultdict(dict)
    for row in rows:
        key = tuple(row[column] for column in group_columns)
        seed = int(row["seed"])
        if seed not in expected or seed in groups[key]:
            raise ValueError(f"unexpected or duplicate seed {seed} in {key}")
        values = {metric: float(row[metric]) for metric in metrics}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"non-finite metric in {key}, seed {seed}")
        groups[key][seed] = values
    result = []
    for key, seeds in sorted(groups.items()):
        if set(seeds) != expected:
            raise ValueError(f"seed coverage missing {expected - set(seeds)} in {key}")
        out = dict(zip(group_columns, key))
        out.update(n_seeds=len(seeds), ddof=ddof)
        for metric in metrics:
            values = [seeds[seed][metric] for seed in sorted(seeds)]
            out[metric + "_mean"] = mean(values)
            out[metric + "_std"] = (stdev if ddof else pstdev)(values)
        result.append(out)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("results/ablation/HARP-model"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"scope": "historical CSV arithmetic and seed coverage only", "files": []}
    for topology, folder in (
        ("vietnam", "harp_ablation_vietnam/worker_vietnam"),
        ("nsfnet", "harp_ablation_results_nsfnet"),
    ):
        for study in ("ablation", "benchmark"):
            raw = args.root / folder / (
                f"{topology}_raw_ablation_5seeds.csv" if study == "ablation"
                else "benchmark_results/all_seed_summary.csv"
            )
            with raw.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            columns = ("topology", "scenario", "key" if study == "ablation" else "algorithm")
            expected_groups = 18 if study == "ablation" else 12
            metrics = ABLATION_METRICS if study == "ablation" else BENCHMARK_METRICS
            summaries = summarize_rows(rows, columns, metrics, SEEDS, int(study == "ablation"))
            expected_scenarios = {"uniform", "bursty", "heavy_tail"} if study == "ablation" else {
                "elephant_stress", "burst_surge", "chaos"
            }
            if len(summaries) != expected_groups or {r["topology"] for r in rows} != {topology}:
                raise ValueError(f"unexpected topology/group coverage: {raw}")
            if {r["scenario"] for r in rows} != expected_scenarios:
                raise ValueError(f"unexpected scenarios: {raw}")
            output = args.output / f"{topology}_{study}_recomputed.csv"
            with output.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
                writer.writeheader()
                writer.writerows(summaries)
            report["files"].append({
                "raw_path": str(raw), "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "rows": len(rows), "groups": len(summaries), "seeds": list(SEEDS),
                "ddof": int(study == "ablation"), "output_path": str(output),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "matched_traces_verified": False, "checkpoint_lineage_verified": False,
            })
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
