#!/usr/bin/env python3
"""Validate and summarize Greedy/DAI action identity against the benchmark rows."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "results/evidence/mentor_completion_20261121/greedy_decoupled"
BENCHMARK = ROOT / "docs/AIO-mesh-rev1/evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv"
OUTPUT = ROOT / "docs/AIO-mesh-rev1/evidence/mentor_completion_20261121/greedy_decoupled_summary.csv"
MANIFEST = OUTPUT.with_name("greedy_decoupled_manifest.json")
SCENARIOS = {"heavy_tail": "elephant_stress", "bursty": "burst_surge", "chaos": "chaos"}
SEEDS = {42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
         11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    with BENCHMARK.open(newline="") as stream:
        benchmark = {
            (row["topology"], row["scenario"], int(row["seed"]), row["algorithm"]): row
            for row in csv.DictReader(stream)
            if row["algorithm"] in {"traditional_greedy_protected", "decoupled_ai_protected"}
            and row["topology"] in {"vietnam", "nsfnet", "geant2"}
        }
    expected = {(topology, scenario, seed) for topology in ("vietnam", "nsfnet", "geant2")
                for scenario in SCENARIOS for seed in SEEDS}
    observed = {}
    for path in AUDIT.glob("*.csv"):
        with path.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 1:
            raise ValueError(f"Expected one row in {path}")
        row = rows[0]
        key = row["topology"], row["scenario"], int(row["seed"])
        if key in observed or path.stem != f"{key[0]}_{key[1]}_{key[2]}":
            raise ValueError(f"Duplicate or mislabeled audit row: {path}")
        if int(row["steps"]) != 3000:
            raise ValueError(f"Unexpected decision count: {path}")
        for field in ("same_placement", "same_route", "same_pair"):
            if not 0 <= int(row[field]) <= 3000:
                raise ValueError(f"Invalid {field}: {path}")
        for algorithm, field in (("traditional_greedy_protected", "greedy_safe_acceptance"),
                                 ("decoupled_ai_protected", "decoupled_safe_acceptance")):
            original = benchmark[key[0], SCENARIOS[key[1]], key[2], algorithm]
            if row["trace_sha256"] != original["trace_sha256"]:
                raise ValueError(f"Trace mismatch: {path}, {algorithm}")
            if abs(float(row[field]) - float(original["safe_acceptance_rate"])) > 1e-9:
                raise ValueError(f"Acceptance mismatch: {path}, {algorithm}")
        observed[key] = row
    if set(observed) != expected:
        raise ValueError(f"Audit coverage: missing={sorted(expected - set(observed))}, "
                         f"unexpected={sorted(set(observed) - expected)}")

    grouped = defaultdict(list)
    for (topology, scenario, _), row in observed.items():
        grouped[topology, scenario].append(row)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ("topology", "scenario", "seeds", "decisions", "same_placement",
              "same_route", "same_pair", "same_placement_pct", "same_pair_pct",
              "seeds_equal_safe_acceptance")
    with OUTPUT.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for key in sorted(grouped):
            rows = grouped[key]
            decisions = sum(int(row["steps"]) for row in rows)
            placement = sum(int(row["same_placement"]) for row in rows)
            route = sum(int(row["same_route"]) for row in rows)
            pair = sum(int(row["same_pair"]) for row in rows)
            writer.writerow(dict(topology=key[0], scenario=key[1], seeds=len(rows),
                                 decisions=decisions, same_placement=placement,
                                 same_route=route, same_pair=pair,
                                 same_placement_pct=100 * placement / decisions,
                                 same_pair_pct=100 * pair / decisions,
                                 seeds_equal_safe_acceptance=sum(
                                     abs(float(row["greedy_safe_acceptance"]) -
                                         float(row["decoupled_safe_acceptance"])) < 1e-9
                                     for row in rows)))
    inputs = [BENCHMARK, Path(__file__), *sorted(AUDIT.glob("*.csv"))]
    MANIFEST.write_text(json.dumps({
        "generator": str(Path(__file__).resolve().relative_to(ROOT)),
        "command": f"python3 {Path(__file__).resolve().relative_to(ROOT)}",
        "scope": "protected Greedy and DAI; separate policy trajectories; paired offered traces",
        "seed_count_per_cell": 20,
        "decisions_per_seed": 3000,
        "inputs_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "output_sha256": {str(OUTPUT.relative_to(ROOT)): sha256(OUTPUT)},
    }, indent=2, sort_keys=True) + "\n")
    print(f"Validated {len(observed)} audit cells against protected benchmark rows; wrote {OUTPUT}")


if __name__ == "__main__":
    main()
