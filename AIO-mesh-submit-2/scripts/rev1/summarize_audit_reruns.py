#!/usr/bin/env python3
"""Summarize the three 2026-11-19 cell reruns and compare available seed rows."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "results/evidence_audit/reruns_20261119"
OUT = ROOT / "docs/AIO-mesh-rev1/evidence/audit_20261119"


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    cases = [
        ("benchmark_vietnam_bursty_seed42", RUNS / "vietnam_bursty_s42/20261119_200939/vietnam_burst_surge_stress/seed_summary.csv"),
        ("ablation_nsfnet_chaos_seed7", RUNS / "nsfnet_chaos_s7/nsfnet/chaos/harp_ablation_summary.csv"),
        ("load_sweep_geant2_1.2_seed2024", RUNS / "geant2_load12_s2024/load_geant2_1.2_2024.csv"),
    ]
    history = read_csv(ROOT / "docs/AIO-mesh-rev1/evidence/load_sweep/all_modes_per_seed.csv")
    out_rows = []
    source_files = []
    for case, path in cases:
        rows = read_csv(path)
        source_files.append({"path": str(path.relative_to(ROOT)), "sha256": file_hash(path), "rows": len(rows)})
        for row in rows:
            if case == "benchmark_vietnam_bursty_seed42" and not row["algorithm"].endswith("_protected"):
                continue
            reference = None
            comparison = "no_original_per_seed_row"
            delta = ""
            if case == "load_sweep_geant2_1.2_seed2024":
                reference = next((x for x in history if x["topology"] == "geant2"
                                  and float(x["load_multiplier"]) == 1.2
                                  and int(x["seed"]) == 2024
                                  and x["algorithm"] == row["algorithm"]), None)
                if reference:
                    delta = float(row["safe_acceptance_rate"]) - float(reference["safe_acceptance_rate"])
                    comparison = "matched_trace_exact_value" if row["trace_sha256"] == reference["trace_sha256"] and delta == 0 else "matched_seed_delta"
            out_rows.append({"case": case, "topology": row.get("topology", ""),
                             "workload": row.get("scenario", ""), "seed": row.get("seed", ""),
                             "method_or_variant": row.get("algorithm", row.get("key", "")),
                             "requests_or_steps": row.get("requests", row.get("steps", "")),
                             "safe_acceptance_rate": row.get("safe_acceptance_rate", ""),
                             "reference_safe_acceptance_rate": reference.get("safe_acceptance_rate", "") if reference else "",
                             "delta_percentage_points": delta,
                             "trace_sha256": row.get("trace_sha256", ""),
                             "reference_trace_sha256": reference.get("trace_sha256", "") if reference else "",
                             "comparison_status": comparison})
    csv_path = OUT / "rerun_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)
    manifest = {"source_commit": "4f6b36549a14564f3220c57619b5bd2690035fe1",
                "procedure": "extract one-seed results; compare load-sweep rows only on topology, load, seed and algorithm; compare trace hashes before calling values exact",
                "inputs": source_files,
                "historical_reference": {"path": "docs/AIO-mesh-rev1/evidence/load_sweep/all_modes_per_seed.csv",
                                         "sha256": file_hash(ROOT / "docs/AIO-mesh-rev1/evidence/load_sweep/all_modes_per_seed.csv")},
                "output": str(csv_path.relative_to(ROOT)), "output_sha256": file_hash(csv_path),
                "rows": len(out_rows)}
    (OUT / "rerun_comparison_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
