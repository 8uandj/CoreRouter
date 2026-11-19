"""Regenerate mentor-requested load-sweep statistics from retained per-seed rows.

This does not execute simulations. It consumes the retained derived per-seed CSV;
original run directories/manifests are currently absent and therefore cannot be
revalidated by this generator.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/AIO-mesh-rev1/evidence/load_sweep"
SOURCE = EVIDENCE / "all_modes_per_seed.csv"
OUT_STATS = EVIDENCE / "mentor_b2_load_sweep_21.csv"
OUT_STATS_TEX = EVIDENCE / "mentor_b2_load_sweep_21.tex"
OUT_UNPROTECTED = EVIDENCE / "mentor_d1_unprotected_load_sweep.csv"
OUT_UNPROTECTED_TEX = EVIDENCE / "mentor_d1_unprotected_load_sweep.tex"
OUT_MANIFEST = EVIDENCE / "mentor_statistics_manifest.json"
TOPOLOGIES = ("vietnam", "nsfnet", "geant2")
LOADS = (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5)
POLICIES = ("traditional_greedy", "decoupled_ai", "saf_h", "harp")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def percentile(values: list[float], p: float) -> float:
    xs = sorted(values)
    if not xs:
        raise ValueError("percentile of empty values")
    pos = (len(xs) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def paired_rank_test(diffs: list[float]) -> dict[str, float | int | None]:
    """Exact two-sided conditional sign-flip Wilcoxon with zero differences dropped.

    Absolute-rank ties use average ranks. An all-zero pair has p=1, n_eff=0,
    rank-biserial undefined, by convention; it remains in the Holm family.
    """
    nz = [float(d) for d in diffs if d != 0.0]
    n_eff = len(nz)
    if n_eff == 0:
        return {"n_effective": 0, "zero_differences": len(diffs),
                "w_plus": 0.0, "w_minus": 0.0, "w_min": 0.0,
                "wilcoxon_exact_p": 1.0, "rank_biserial": None}

    ordered = sorted((abs(d), i) for i, d in enumerate(nz))
    ranks = [0.0] * n_eff
    i = 0
    while i < n_eff:
        j = i + 1
        while j < n_eff and ordered[j][0] == ordered[i][0]:
            j += 1
        avg_rank = ((i + 1) + j) / 2.0
        for _, original_idx in ordered[i:j]:
            ranks[original_idx] = avg_rank
        i = j

    w_plus = sum(rank for d, rank in zip(nz, ranks) if d > 0)
    total_rank = sum(ranks)
    w_minus = total_rank - w_plus
    observed_distance = abs(w_plus - total_rank / 2)

    # DP over doubled average ranks yields the exact sign-flip distribution,
    # including tied absolute differences, without floating-point state keys.
    doubled = [int(round(2 * rank)) for rank in ranks]
    counts = Counter({0: 1})
    for rank2 in doubled:
        next_counts = Counter(counts)
        for s, count in counts.items():
            next_counts[s + rank2] += count
        counts = next_counts
    center2 = sum(doubled)
    obs2 = int(round(2 * w_plus))
    threshold = abs(2 * obs2 - center2)
    extreme = sum(count for s, count in counts.items()
                  if abs(2 * s - center2) >= threshold)
    p = min(1.0, extreme / (2 ** n_eff))
    r_rb = (w_plus - w_minus) / total_rank if total_rank else None
    return {"n_effective": n_eff, "zero_differences": len(diffs) - n_eff,
            "w_plus": w_plus, "w_minus": w_minus,
            "w_min": min(w_plus, w_minus), "wilcoxon_exact_p": p,
            "rank_biserial": r_rb}


def bootstrap_ci(diffs: list[float], seed: int, reps: int = 20000) -> tuple[float, float]:
    if all(d == diffs[0] for d in diffs):
        return diffs[0], diffs[0]
    rng = random.Random(seed)
    n = len(diffs)
    means = [sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps)]
    return percentile(means, 0.025), percentile(means, 0.975)


def holm(pvalues: list[float]) -> list[float]:
    order = sorted(range(len(pvalues)), key=lambda i: (pvalues[i], i))
    adjusted = [0.0] * len(pvalues)
    running = 0.0
    m = len(pvalues)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[idx]))
        adjusted[idx] = running
    return adjusted


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    groups: dict[tuple[str, float, str], dict[int, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        topology = row["topology"]
        load = float(row["load_multiplier"])
        alg = row["algorithm"]
        seed = int(row["seed"])
        key = (topology, load, alg)
        if seed in groups[key]:
            raise ValueError(f"duplicate row for {key}, seed={seed}")
        groups[key][seed] = row

    # Verify the full 3 × 7 × 8 matrix, 20 seeds, common trace per paired policy.
    expected_modes = {f"{p}_{guard}" for p in POLICIES for guard in ("protected", "unprotected")}
    seeds_by_group = set(range(1))  # replaced after reading actual seed labels
    del seeds_by_group
    seed_sets = set()
    trace_mismatches = []
    for topology in TOPOLOGIES:
        for load in LOADS:
            for mode in expected_modes:
                group = groups.get((topology, load, mode), {})
                if len(group) != 20:
                    raise ValueError(f"expected 20 rows: {topology} load={load} {mode}; found {len(group)}")
                seed_sets.add(tuple(sorted(group)))
            for protection in ("protected", "unprotected"):
                for policy in POLICIES:
                    g = groups[(topology, load, f"{policy}_{protection}")]
                    seed_sets.add(tuple(sorted(g)))
            # Compare trace hashes across all eight modes for each seed.
            by_seed: dict[int, set[str]] = defaultdict(set)
            for mode in expected_modes:
                for seed, row in groups[(topology, load, mode)].items():
                    by_seed[seed].add(row["trace_sha256"])
            for seed, hashes in by_seed.items():
                if len(hashes) != 1:
                    trace_mismatches.append((topology, load, seed, sorted(hashes)))
    if trace_mismatches:
        raise ValueError(f"trace mismatch across policy modes: {trace_mismatches[:3]}")
    if len(seed_sets) != 1:
        raise ValueError("seed sets differ between cells")

    stats_rows = []
    for topology in TOPOLOGIES:
        for load in LOADS:
            treatment = groups[(topology, load, "harp_protected")]
            control = groups[(topology, load, "saf_h_protected")]
            seeds = sorted(treatment)
            diffs = [float(treatment[s]["safe_acceptance_rate"]) -
                     float(control[s]["safe_acceptance_rate"]) for s in seeds]
            ci_low, ci_high = bootstrap_ci(diffs, seed=20261119 + TOPOLOGIES.index(topology) * 31 + LOADS.index(load))
            test = paired_rank_test(diffs)
            row = {
                "topology": topology, "load_multiplier": f"{load:.1f}",
                "outcome": "HARP minus SAF-H safe acceptance (percentage points)",
                "n_pairs": len(diffs), "mean_delta_pp": statistics.mean(diffs),
                "bootstrap_ci95_low_pp": ci_low, "bootstrap_ci95_high_pp": ci_high,
                **test,
                "all_pairs_identical": int(all(d == 0 for d in diffs)),
                "zero_ci_p_convention": "all-zero: CI=[0,0], exact p=1, Holm includes p=1, rank-biserial undefined",
            }
            stats_rows.append(row)
    adjusted = holm([float(r["wilcoxon_exact_p"]) for r in stats_rows])
    for row, adj in zip(stats_rows, adjusted):
        row["holm_p_21"] = adj

    with OUT_STATS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(stats_rows[0]))
        w.writeheader(); w.writerows(stats_rows)
    tex = [
        r"\begin{table*}[p]", r"\centering", r"\color{revisiongreen}\small",
        r"\begin{tabular}{llrrrrrr}",
        r"\toprule",
        r"Topology & Intensity & $\Delta$ (pp) & 95\% CI & $p$ & $r_{rb}$ & $n_{eff}$ & $p_{\mathrm{Holm}}$ \\",
        r"\midrule",
    ]
    for row in stats_rows:
        ci = f"[{row['bootstrap_ci95_low_pp']:.3f}, {row['bootstrap_ci95_high_pp']:.3f}]"
        effect = "--" if row["rank_biserial"] is None else f"{row['rank_biserial']:.3f}"
        tex.append(
            f"{row['topology'].upper()} & {float(row['load_multiplier']):.1f} & "
            f"{row['mean_delta_pp']:.3f} & {ci} & {row['wilcoxon_exact_p']:.3g} & "
            f"{effect} & {row['n_effective']} & {row['holm_p_21']:.3g} " + r"\\"
        )
    tex.extend([r"\bottomrule", r"\end{tabular}",
                r"\caption{Paired HARP--SAF-H safe-acceptance differences in the load sweep. $\Delta$ is the mean over matched seeds; CI is the 20,000-resample paired percentile-bootstrap 95\% interval. $p$ is the exact two-sided Wilcoxon signed-rank p-value with zero differences dropped and tied absolute ranks averaged. All-zero comparisons use $p_H=1$, $n_{eff}=0$, and undefined $r_{rb}$, and remain in the 21-test Holm family.}",
                r"\label{tab:load_sweep_paired_statistics}", r"\end{table*}"])
    OUT_STATS_TEX.write_text("\n".join(tex) + "\n", encoding="utf-8")

    unprotected_rows = []
    metrics = {
        "admitted_cpu_violation_rate": "CPU",
        "admitted_ram_violation_rate": "RAM",
        "admitted_bw_violation_rate": "BW",
        "msd_violation_rate": "MSD",
        "admitted_hard_violation_rate": "unique hard-violation union",
    }
    for topology in TOPOLOGIES:
        for load in LOADS:
            for policy in POLICIES:
                group = groups[(topology, load, f"{policy}_unprotected")]
                output = {"topology": topology, "load_multiplier": f"{load:.1f}",
                          "policy": policy, "n_seed_runs": len(group),
                          "denominator": "offered non-skipped requests; rates are percentages"}
                for field, label in metrics.items():
                    values = [float(r[field]) for r in group.values()]
                    output[f"{label}_mean_pct"] = statistics.mean(values)
                    output[f"{label}_sample_sd_pp"] = statistics.stdev(values)
                unprotected_rows.append(output)
    with OUT_UNPROTECTED.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(unprotected_rows[0]))
        w.writeheader(); w.writerows(unprotected_rows)
    tex = []
    for index, topology in enumerate(TOPOLOGIES):
        tex.extend([
            r"\begin{table*}[p]", r"\centering", r"\color{revisiongreen}\small",
            r"\begin{tabular}{llrrrrr}", r"\toprule",
            r"Intensity & Policy & CPU & RAM & BW & MSD & Any hard violation \\",
            r"\midrule",
        ])
        for row in unprotected_rows:
            if row["topology"] != topology:
                continue
            display = {"traditional_greedy": "Greedy", "decoupled_ai": "DAI",
                       "saf_h": "SAF-H", "harp": "HARP"}[row["policy"]]
            cells = [f"{row[f'{metric}_mean_pct']:.3f} $\\pm$ {row[f'{metric}_sample_sd_pp']:.3f}"
                     for metric in ("CPU", "RAM", "BW", "MSD", "unique hard-violation union")]
            tex.append(f"{float(row['load_multiplier']):.1f} & {display} & "
                       + " & ".join(cells) + " " + r"\\")
        title = "Vietnam" if topology == "vietnam" else topology.upper()
        label = "tab:load_sweep_unprotected" if index == 0 else f"tab:load_sweep_unprotected_{topology}"
        tex.extend([
            r"\bottomrule", r"\end{tabular}",
            fr"\caption{{\newrev{{{title} offered-intensity experiment with admission disabled. Rates are means and sample SD in percent over 20 seeds. The denominator is all offered requests. Constraint categories can overlap.}}}}",
            fr"\label{{{label}}}", r"\end{table*}",
        ])
    OUT_UNPROTECTED_TEX.write_text("\n".join(tex) + "\n", encoding="utf-8")

    raw_dir = ROOT / "results/rev1/load_sweep/current_code_20261117"
    manifest = {
        "generator": str(Path(__file__).resolve().relative_to(ROOT)),
        "input": str(SOURCE.relative_to(ROOT)), "input_sha256": sha256(SOURCE),
        "input_rows": len(rows), "coverage": "3 topologies × 7 loads × 8 policy/protection modes × 20 seeds",
        "paired_traces_verified_from_retained_csv": True,
        "original_run_directory_present": raw_dir.exists(),
        "original_run_manifests_present": list(str(p.relative_to(ROOT)) for p in raw_dir.rglob("*manifest*.json")) if raw_dir.exists() else [],
        "statistical_method": {
            "mean_difference_ci": "20,000-replicate paired percentile bootstrap; deterministic per topology/load",
            "wilcoxon": "exact two-sided sign-flip distribution; zero differences dropped; tied absolute differences receive average ranks",
            "all_zero_case": "n_effective=0, W+=W-=0, exact p=1, CI=[0,0], rank-biserial undefined; p=1 included in 21-test Holm family",
            "rank_biserial": "(W+ - W-)/(W+ + W-) after zero pairs are dropped",
            "holm_family_size": 21,
        },
        "outputs": [str(p.relative_to(ROOT)) for p in
                    (OUT_STATS, OUT_STATS_TEX, OUT_UNPROTECTED, OUT_UNPROTECTED_TEX)],
        "limitation": "The original results/rev1/load_sweep/current_code_20261117/ inputs cited by the earlier README are absent. These statistics are reproducible from the retained derived CSV, but original run hashes/manifests cannot be revalidated.",
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(stats_rows)} paired rows and {len(unprotected_rows)} unprotected load cells from {len(rows)} retained rows.")
    print(f"all-zero comparisons: {sum(int(r['all_pairs_identical']) for r in stats_rows)}")
    print(f"original raw result directory present: {raw_dir.exists()}")


if __name__ == "__main__":
    main()
