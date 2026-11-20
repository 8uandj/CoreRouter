#!/usr/bin/env python3
"""Validate and summarize a completed six-topology benchmark evidence run."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

TOPOLOGIES = ("vietnam", "nsfnet", "geant2", "synthetic_25", "synthetic_50", "synthetic_100")
SCENARIOS = ("elephant_stress", "burst_surge", "chaos")
SEEDS = (42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
         11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192)
BASELINES = ("traditional_greedy_protected", "decoupled_ai_protected", "cspf_protected", "saf_h_protected")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows):
    if not rows:
        raise ValueError("refusing to emit an empty summary")
    with path.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def exact_wilcoxon(differences):
    """Exact two-sided sign-flip Wilcoxon; drops zeroes and averages rank ties."""
    diffs = [float(d) for d in differences if float(d) != 0.0]
    if not diffs:
        return {"n_effective": 0, "zero_differences": len(differences),
                "w_plus": 0.0, "rank_biserial": None, "p": 1.0}
    ordered = sorted((abs(d), i) for i, d in enumerate(diffs))
    ranks = [0.0] * len(diffs)
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        rank = ((i + 1) + j) / 2.0
        for _, idx in ordered[i:j]:
            ranks[idx] = rank
        i = j
    w_plus = sum(r for d, r in zip(diffs, ranks) if d > 0)
    total = sum(ranks)
    doubled = [int(round(2 * r)) for r in ranks]
    counts = {0: 1}
    for rank in doubled:
        nxt = dict(counts)
        for value, count in counts.items():
            nxt[value + rank] = nxt.get(value + rank, 0) + count
        counts = nxt
    threshold = abs(4 * int(round(2 * w_plus)) - 2 * sum(doubled))
    extreme = sum(count for value, count in counts.items()
                  if abs(4 * value - 2 * sum(doubled)) >= threshold)
    return {"n_effective": len(diffs), "zero_differences": len(differences) - len(diffs),
            "w_plus": w_plus, "rank_biserial": (2 * w_plus - total) / total,
            "p": min(1.0, extreme / (2 ** len(diffs)))}


def bootstrap_ci(differences, seed, replicates=20000):
    if all(x == differences[0] for x in differences):
        return differences[0], differences[0]
    rng = random.Random(seed)
    n = len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(replicates))
    def pct(p):
        pos = (len(means) - 1) * p
        lo, hi = math.floor(pos), math.ceil(pos)
        return means[lo] + (means[hi] - means[lo]) * (pos - lo)
    return pct(0.025), pct(0.975)


def holm(pvalues):
    order = sorted(range(len(pvalues)), key=lambda i: (pvalues[i], i))
    adjusted, running = [0.0] * len(pvalues), 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[idx]))
        adjusted[idx] = running
    return adjusted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    out = (args.output or (root / "analysis")).resolve()
    if out.exists():
        raise FileExistsError("summary output exists; choose a fresh --output path")
    out.mkdir(parents=True)

    all_rows, run_inputs = [], []
    for topology in TOPOLOGIES:
        candidates = list((root / topology).glob("*/run_manifest.json"))
        complete = [path for path in candidates if (path.parent / "all_seed_summary.csv").is_file()]
        if len(complete) != 1:
            raise ValueError("expected one completed benchmark attempt under %s, found %s; total attempts=%s" %
                             (topology, len(complete), len(candidates)))
        run_manifest_path = complete[0]
        run_root = run_manifest_path.parent
        manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        if tuple(manifest.get("seeds", ())) != SEEDS or manifest.get("steps") != 3000:
            raise ValueError("seed/step protocol mismatch for %s" % topology)
        jobs = {j[0] for j in manifest.get("scenario_jobs", [])}
        if jobs != set(SCENARIOS):
            raise ValueError("workload coverage mismatch for %s: %r" % (topology, jobs))
        all_seed_path = run_root / "all_seed_summary.csv"
        rows = csv_rows(all_seed_path)
        expected_scenarios = {"elephant_stress", "burst_surge", "chaos"}
        seen = defaultdict(set)
        traces = defaultdict(set)
        for row in rows:
            key = (row["scenario"], row["algorithm"])
            seed = int(row["seed"])
            if seed in seen[key]:
                raise ValueError("duplicate per-seed row: %s %s seed %s" % (*key, seed))
            seen[key].add(seed)
            if row["topology"] != topology:
                raise ValueError("wrong topology in seed summary")
            if int(row["requests"]) != 3000 or not row.get("trace_sha256"):
                raise ValueError("missing offered requests or trace hash in %s/%s/%s" % (topology, *key))
            all_rows.append(row)
            traces[(row["scenario"], seed)].add(row["trace_sha256"])
        algorithms = {r["algorithm"] for r in rows}
        expected_algorithms = {f"{name}_{mode}" for name in
                               ("traditional_greedy", "decoupled_ai", "cspf", "saf_h", "harp")
                               for mode in ("protected", "unprotected")}
        if algorithms != expected_algorithms:
            raise ValueError("policy coverage mismatch for %s: %s" % (topology, algorithms))
        for scenario in expected_scenarios:
            for algorithm in algorithms:
                if seen[(scenario, algorithm)] != set(SEEDS):
                    raise ValueError("incomplete seed coverage for %s/%s/%s" % (topology, scenario, algorithm))
            for seed in SEEDS:
                if len(traces[(scenario, seed)]) != 1:
                    raise ValueError("offered trace mismatch across policies for %s/%s/seed %s" %
                                     (topology, scenario, seed))
        art = manifest["artifacts"][topology]
        for k in ("model_path", "normalizer_path"):
            path = Path(art[k])
            if not path.is_absolute():
                path = Path.cwd() / path
            expected_hash = art[k.replace("_path", "_sha256")]
            if sha256(path) != expected_hash:
                raise ValueError("artifact hash changed: %s" % path)
        run_inputs.append({"topology": topology,
                           "attempts": [{"run_manifest": str(path), "run_manifest_sha256": sha256(path),
                                         "completed": (path.parent / "all_seed_summary.csv").is_file()}
                                        for path in candidates],
                           "selected_completed_run_manifest": str(run_manifest_path),
                           "selected_run_manifest_sha256": sha256(run_manifest_path),
                           "per_seed_csv": str(all_seed_path), "per_seed_sha256": sha256(all_seed_path),
                           "rows": len(rows), "algorithms": sorted(algorithms)})

    per_seed_path = out / "all_six_topologies_per_seed.csv"
    write_csv(per_seed_path, all_rows)

    groups = defaultdict(list)
    for row in all_rows:
        groups[(row["topology"], row["scenario"], row["algorithm"])].append(row)
    metric_names = ("safe_acceptance_rate", "acceptance_rate", "admitted_hard_violation_rate",
                    "msd_violation_rate", "sla_violation_rate", "avg_latency_ms", "p95_latency_ms",
                    "avg_reward", "decision_latency_p95_ms", "mask_empty_rate")
    summary = []
    for (topology, scenario, algorithm), rows in sorted(groups.items()):
        item = {"topology": topology, "scenario": scenario, "algorithm": algorithm, "n_seed": len(rows)}
        for metric in metric_names:
            vals = [float(r[metric]) for r in rows if r.get(metric) not in (None, "")]
            if vals:
                item[metric + "_mean"] = statistics.mean(vals)
                item[metric + "_sample_sd"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
            else:
                item[metric + "_mean"] = ""
                item[metric + "_sample_sd"] = ""
        summary.append(item)
    summary_path = out / "summary_by_topology_workload_policy.csv"
    write_csv(summary_path, summary)

    paired = []
    for topology in TOPOLOGIES:
        for scenario in SCENARIOS:
            lookup = {r["algorithm"]: {int(x["seed"]): float(x["safe_acceptance_rate"])
                                       for x in groups[(topology, scenario, r["algorithm"])]}
                      for r in summary if r["topology"] == topology and r["scenario"] == scenario}
            best = max(BASELINES, key=lambda alg: statistics.mean(lookup[alg].values()))
            for comparison, control in (("harp_vs_saf_h", "saf_h_protected"),
                                        ("harp_vs_strongest_protected_baseline", best)):
                diffs = [lookup["harp_protected"][seed] - lookup[control][seed] for seed in SEEDS]
                test = exact_wilcoxon(diffs)
                low, high = bootstrap_ci(diffs, seed=20261120 + TOPOLOGIES.index(topology) * 31 + SCENARIOS.index(scenario))
                paired.append({"topology": topology, "scenario": scenario, "comparison": comparison,
                               "treatment": "harp_protected", "control": control,
                               "strongest_baseline_selected_by_mean": best,
                               "n_seed": len(diffs), "n_effective": test["n_effective"],
                               "zero_differences": test["zero_differences"],
                               "mean_delta_safe_acceptance_pp": statistics.mean(diffs),
                               "sample_sd_delta_pp": statistics.stdev(diffs),
                               "bootstrap_ci95_low_pp": low, "bootstrap_ci95_high_pp": high,
                               "w_plus": test["w_plus"], "wilcoxon_exact_p": test["p"],
                               "rank_biserial": test["rank_biserial"], "trace_hashes_paired": True})
    for comparison in {r["comparison"] for r in paired}:
        subset = [r for r in paired if r["comparison"] == comparison]
        adjusted = holm([r["wilcoxon_exact_p"] for r in subset])
        for row, p_adj in zip(subset, adjusted):
            row["holm_p_family_18"] = p_adj
    paired_path = out / "paired_statistics.csv"
    write_csv(paired_path, paired)
    summary_manifest = {"evidence_root": str(root), "source_commit": "4f6b36549a14564f3220c57619b5bd2690035fe1",
                        "protocol": "20 seeds x 3000 steps x 3 stress workloads x 6 topologies",
                        "aggregation": "mean and sample SD across seed-level run summaries",
                        "paired_statistics": "HARP safe acceptance; exact two-sided signed-rank, drops zeros, averages tied absolute ranks; 20,000 paired percentile-bootstrap resamples; Holm correction separately across 18 topology-workload tests for each comparison family",
                        "inputs": run_inputs,
                        "outputs": {p.name: sha256(p) for p in (per_seed_path, summary_path, paired_path)},
                        "per_seed_rows": len(all_rows)}
    (out / "summary_manifest.json").write_text(json.dumps(summary_manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary_dir": str(out), "per_seed_rows": len(all_rows),
                      "summary_rows": len(summary), "paired_tests": len(paired)}, indent=2))


if __name__ == "__main__":
    main()
