#!/usr/bin/env python3
"""Export retained SAF-H grid timing per seed with source hashes."""

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "results/rev1/nonhil_studies/20261117_235132"
EVIDENCE = ROOT / "docs/AIO-mesh-rev1/evidence/mentor_completion_20261121"
OUTPUT = EVIDENCE / "grid_timing_per_seed.csv"
MANIFEST = EVIDENCE / "grid_timing_archive_manifest.json"
FIELDS = ("topology", "seed", "requests", "feasible_set_ms_p50_ms",
          "feasible_set_ms_p95_ms", "feasible_set_ms_p99_ms",
          "heuristic_selection_ms_p95_ms", "state_construction_ms_p95_ms",
          "admission_validation_ms_p95_ms", "environment_step_ms_p95_ms",
          "decision_latency_p95_ms", "decision_latency_p99_ms")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    source = ARCHIVE / "topology_scalability.json"
    data = json.loads(source.read_text())
    if data["policy"] != "SAF-H" or data["steps_per_seed"] != 300:
        raise ValueError("Unexpected archived timing protocol")
    seeds = set(data["seeds"])
    if len(seeds) != 10:
        raise ValueError("Expected 10 distinct timing seeds")
    rows = data["per_seed"]
    expected = {(f"synthetic_{n}", seed) for n in (25, 50, 100) for seed in seeds}
    observed = [(row["topology"], row["seed"]) for row in rows]
    if len(rows) != 30 or len(set(observed)) != 30 or set(observed) != expected:
        raise ValueError("Incomplete or duplicated grid timing rows")
    if any(int(row["requests"]) != 300 for row in rows):
        raise ValueError("Grid timing row has unexpected request count")
    for aggregate in data["measurements"]:
        group = [row for row in rows if row["topology"] == aggregate["topology"]]
        for source_field, reported_field in (
            ("feasible_set_ms_p50_ms", "feasible_set_p50_ms_mean"),
            ("feasible_set_ms_p95_ms", "feasible_set_p95_ms_mean"),
            ("heuristic_selection_ms_p95_ms", "selection_p95_ms_mean"),
            ("decision_latency_p95_ms", "decision_p95_ms_mean"),
        ):
            recalculated = sum(float(row[source_field]) for row in group) / len(group)
            if abs(recalculated - float(aggregate[reported_field])) > 1e-9:
                raise ValueError(f"Aggregate mismatch: {aggregate['topology']} {source_field}")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["topology"], r["seed"])):
            writer.writerow({field: row[field] for field in FIELDS})
    inputs = [ARCHIVE / "manifest.json", source, Path(__file__).resolve()]
    MANIFEST.write_text(json.dumps({
        "scope": "Historical serialized SAF-H timing; 10 seeds x 3 synthetic grids; not refreshed HARP timing",
        "command": f"python3 {Path(__file__).resolve().relative_to(ROOT)}",
        "inputs_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "output_sha256": {str(OUTPUT.relative_to(ROOT)): sha256(OUTPUT)},
    }, indent=2, sort_keys=True) + "\n")
    print(f"Exported {len(rows)} validated timing rows: {OUTPUT}")


if __name__ == "__main__":
    main()
