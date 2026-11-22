#!/usr/bin/env python3
"""Generate paired HARP--SAF-H statistics for the fixed-profile arrival sweep."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

from summarize_mentor_statistics import bootstrap_ci, holm, paired_rank_test

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "results/evidence/mentor_completion_20261121/arrival_rate_only"
RAW = EVIDENCE / "arrival_rate_per_seed.csv"
AGGREGATE = EVIDENCE / "arrival_rate_aggregate.csv"
OUT = ROOT / "docs/AIO-mesh-rev1/evidence/mentor_completion_20261121"
TEX = ROOT / "docs/AIO-mesh-rev1/generated/arrival_rate_paired_rows.tex"
FIGURE = ROOT / "docs/AIO-mesh-rev1/figs/arrival_rate_only.pdf"
TOPOLOGIES = ("vietnam", "nsfnet", "geant2")
RATES = (0.2, 0.4, 0.6, 0.8, 1.0)
SEEDS = (42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
         11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    with RAW.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    groups: dict[tuple[str, float, str], dict[int, float]] = {}
    for row in rows:
        key = (row["topology"], float(row["arrival_rate"]), row["algorithm"])
        seed = int(row["seed"])
        group = groups.setdefault(key, {})
        if seed in group:
            raise ValueError(f"duplicate seed row: {key}, seed={seed}")
        # RunMetrics already stores acceptance in percentage points.
        group[seed] = float(row["safe_acceptance_rate"])

    results = []
    for topology in TOPOLOGIES:
        for rate_index, rate in enumerate(RATES):
            harp = groups[(topology, rate, "harp_protected")]
            safh = groups[(topology, rate, "saf_h_protected")]
            if set(harp) != set(SEEDS) or set(safh) != set(SEEDS):
                raise ValueError(f"incomplete paired seeds for {topology}/{rate}")
            diffs = [harp[seed] - safh[seed] for seed in SEEDS]
            test = paired_rank_test(diffs)
            low, high = bootstrap_ci(
                diffs, seed=20261122 + TOPOLOGIES.index(topology) * 31 + rate_index,
                reps=20_000)
            results.append({
                "topology": topology,
                "arrival_rate": rate,
                "n_seeds": len(diffs),
                "harp_mean_pct": statistics.mean(harp.values()),
                "saf_h_mean_pct": statistics.mean(safh.values()),
                "mean_difference_pp": statistics.mean(diffs),
                "difference_sd_pp": statistics.stdev(diffs),
                "ci95_low_pp": low,
                "ci95_high_pp": high,
                **test,
            })

    adjusted = holm([row["wilcoxon_exact_p"] for row in results])
    for row, p_holm in zip(results, adjusted):
        row["holm_p_family_15"] = p_holm

    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "arrival_rate_harp_safh_paired.csv"
    fields = list(results[0])
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)

    lines = []
    for row in results:
        lines.append(
            f"{row['topology'].upper()} & {row['arrival_rate']:.1f} & "
            f"{row['mean_difference_pp']:.3f} & "
            f"[{row['ci95_low_pp']:.3f}, {row['ci95_high_pp']:.3f}] & "
            f"{row['wilcoxon_exact_p']:.3g} & {row['holm_p_family_15']:.3g} "
            + r"\\"
        )
    TEX.parent.mkdir(parents=True, exist_ok=True)
    TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    source_figure = EVIDENCE / "arrival_rate_only.pdf"
    FIGURE.write_bytes(source_figure.read_bytes())

    manifest = {
        "scope": "Matched-seed HARP minus SAF-H safe-acceptance contrasts in the fixed-profile arrival-rate-only experiment",
        "protocol_manifest": str((EVIDENCE / "arrival_rate_manifest.json").relative_to(ROOT)),
        "raw_rows": str(RAW.relative_to(ROOT)),
        "aggregate_rows": str(AGGREGATE.relative_to(ROOT)),
        "seeds": list(SEEDS),
        "topologies": list(TOPOLOGIES),
        "arrival_rates": list(RATES),
        "paired_tests": "exact two-sided signed-rank test; zero differences dropped; tied absolute ranks averaged",
        "confidence_intervals": "20,000 paired percentile-bootstrap resamples; deterministic per topology and arrival rate",
        "multiplicity": "Holm correction across all 15 topology-by-arrival-rate contrasts",
        "inputs_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (RAW, AGGREGATE, EVIDENCE / "arrival_rate_manifest.json", Path(__file__).resolve())
        },
        "outputs_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (csv_path, TEX, FIGURE)
        },
    }
    manifest_path = OUT / "arrival_rate_paired_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Summarized {len(rows)} raw rows into {len(results)} paired contrasts")
    print(f"Wrote {csv_path.relative_to(ROOT)} and {TEX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
