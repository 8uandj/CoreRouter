#!/usr/bin/env python3
"""Validate paired mask-expiry intervention against refreshed benchmark."""
import csv
import hashlib
import json
import random
import statistics
from pathlib import Path

from summarize_mentor_statistics import bootstrap_ci, holm, paired_rank_test

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results/evidence/mentor_completion_20261121/mask_expiry_intervention"
BENCH = ROOT / "docs/AIO-mesh-rev1/evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv"
OUT = ROOT / "docs/AIO-mesh-rev1/evidence/mentor_completion_20261121"
SEEDS = {42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
         11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    with BENCH.open(newline="") as f:
        benchmark = {(r["topology"], int(r["seed"])): r for r in csv.DictReader(f)
                     if r["algorithm"] == "harp_protected" and r["scenario"] == "burst_surge"
                     and r["topology"] in {"vietnam", "nsfnet", "geant2"}}
    groups = {topo: {} for topo in ("vietnam", "nsfnet", "geant2")}
    raw_files = sorted(RAW.glob("*.csv"))
    if len(raw_files) != 60:
        raise ValueError(f"Expected 60 paired cells; found {len(raw_files)}")
    for path in raw_files:
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 2 or {r["mode"] for r in rows} != {"pre_expiry", "post_expiry_mask"}:
            raise ValueError(f"Invalid mode rows: {path}")
        by_mode = {r["mode"]: r for r in rows}
        before, after = by_mode["pre_expiry"], by_mode["post_expiry_mask"]
        topo, seed = before["topology"], int(before["seed"])
        if topo not in groups or seed not in SEEDS or seed in groups[topo]:
            raise ValueError(f"Unexpected or duplicate cell: {path}")
        if path.stem != f"{topo}_{seed}" or after["topology"] != topo or int(after["seed"]) != seed:
            raise ValueError(f"Filename or cell mismatch: {path}")
        original = benchmark[topo, seed]
        if (before["trace_sha256"] != after["trace_sha256"]
                or before["trace_sha256"] != original["trace_sha256"]):
            raise ValueError(f"Offered trace mismatch: {path}")
        if abs(float(before["safe_acceptance_rate"]) - float(original["safe_acceptance_rate"])) > 1e-9:
            raise ValueError(f"Current-policy acceptance mismatch: {path}")
        if int(before["requests"]) != 3000 or int(after["requests"]) != 3000:
            raise ValueError(f"Unexpected request count: {path}")
        groups[topo][seed] = before, after
    if any(set(group) != SEEDS for group in groups.values()):
        raise ValueError("Incomplete per-topology seed coverage")

    rows = []
    for index, (topo, group) in enumerate(groups.items()):
        before = [float(group[seed][0]["safe_acceptance_rate"]) for seed in sorted(group)]
        after = [float(group[seed][1]["safe_acceptance_rate"]) for seed in sorted(group)]
        delta = [b - a for a, b in zip(before, after)]
        low, high = bootstrap_ci(delta, seed=20261122 + index, reps=20000)
        test = paired_rank_test(delta)
        rows.append(dict(topology=topo, scenario="bursty", seeds=20, requests_per_seed=3000,
                         pre_mean_pct=statistics.mean(before), post_mean_pct=statistics.mean(after),
                         mean_delta_pp=statistics.mean(delta), sample_sd_delta_pp=statistics.stdev(delta),
                         ci95_low_pp=low, ci95_high_pp=high,
                         positive_seeds=sum(x > 0 for x in delta),
                         negative_seeds=sum(x < 0 for x in delta),
                         zero_seeds=sum(x == 0 for x in delta),
                         wilcoxon_exact_p=test["wilcoxon_exact_p"],
                         n_effective=test["n_effective"]))
    adjusted = holm([r["wilcoxon_exact_p"] for r in rows])
    for row, p in zip(rows, adjusted):
        row["holm_p"] = p
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / "mask_expiry_intervention_summary.csv"
    with output.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    inputs = [BENCH, Path(__file__).resolve(), ROOT / "scripts/rev1/summarize_mentor_statistics.py", *raw_files]
    manifest = OUT / "mask_expiry_intervention_manifest.json"
    manifest.write_text(json.dumps({
        "scope": "Matched offered traces, separate policy trajectories; post-expiry mask with pre-expiry observation; no runtime code change",
        "command": f"python3 {Path(__file__).resolve().relative_to(ROOT)}",
        "inputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in inputs},
        "output_sha256": {str(output.relative_to(ROOT)): sha256(output)},
    }, indent=2, sort_keys=True) + "\n")
    print(f"Validated {len(raw_files)} paired cells against benchmark; wrote {output}")


if __name__ == "__main__":
    main()
