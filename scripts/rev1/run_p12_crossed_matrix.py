#!/usr/bin/env python3
"""Run the matched synthetic-topology x modeled-occupancy timing matrix."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics.benchmark.benchmark_algorithm import run_load_sweep as load_sweep
from src.analytics.benchmark.benchmark_algorithm.algorithms import run_jo_vppm, run_saf_h
from src.analytics.benchmark.revision.provenance import sha256_file


SEEDS = [7, 11, 17, 23, 42, 47, 73, 89, 100, 101,
         211, 314, 512, 1024, 2024, 2718, 4096, 8192, 8888, 9999]
TOPOLOGIES = ("synthetic_25", "synthetic_50", "synthetic_100")
OCCUPANCIES = (0, 25, 50, 100)


def run_protected_pair(make_env_fn, scenario, steps, seed, model_path, norm_path,
                       include_exhaustive=False, include_unprotected=False):
    del include_exhaustive, include_unprotected
    return {
        "harp_protected": run_jo_vppm(
            make_env_fn, model_path, norm_path, scenario, steps, seed, protected=True
        ),
        "saf_h_protected": run_saf_h(
            make_env_fn, scenario, steps, seed, protected=True
        ),
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def run_cell_seed(topology: str, occupancy: int, seed: int, args, model: Path,
                  normalizer: Path) -> dict[str, Any]:
    # Reuse the established sweep's environment factory, offered-load trace,
    # background-chain seeding, and per-policy metric collection at load=1.0.
    original = load_sweep.run_all_algorithms
    load_sweep.run_all_algorithms = run_protected_pair
    try:
        rows = load_sweep.run_sweep(
            topology, [1.0], args.steps, [seed], args.data_path, model, normalizer,
            active_chains=occupancy,
        )
    finally:
        load_sweep.run_all_algorithms = original
    rows = [dict(row, topology=topology, active_chains=occupancy,
                 seed=seed, load_multiplier=1.0) for row in rows]
    by_policy = {row["algorithm"]: row for row in rows}
    if set(by_policy) != {"harp_protected", "saf_h_protected"}:
        raise RuntimeError(f"unexpected policy coverage: {sorted(by_policy)}")
    if by_policy["harp_protected"].get("trace_sha256") != by_policy["saf_h_protected"].get("trace_sha256"):
        raise RuntimeError(f"matched trace hash mismatch: {topology}, {occupancy}, seed={seed}")
    return {
        "topology": topology,
        "nodes": int(topology.rsplit("_", 1)[1]),
        "active_chains": occupancy,
        "load_multiplier": 1.0,
        "steps": args.steps,
        "seed": seed,
        "trace_sha256": by_policy["harp_protected"]["trace_sha256"],
        "policies": rows,
    }


def write_aggregates(out_dir: Path) -> tuple[int, int]:
    cell_files = sorted(out_dir.glob("synthetic_*/chains_*/seed_*.json"))
    rows = []
    for path in cell_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["policies"]:
            rows.append(row)
    if not rows:
        return 0, 0
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (out_dir / "per_seed.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    group_keys = ("topology", "nodes", "active_chains", "load_multiplier", "algorithm")
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row.get(k) for k in group_keys)
        groups.setdefault(key, []).append(row)
    timing_columns = sorted({k for row in rows for k in row if k.endswith("_p50_ms")
                             or k.endswith("_p95_ms") or k.endswith("_p99_ms")})
    summaries = []
    for key, group in sorted(groups.items(), key=lambda item: item[0]):
        result = dict(zip(group_keys, key))
        result["seeds"] = len(group)
        for column in timing_columns:
            values = [float(row[column]) for row in group if row.get(column) not in (None, "")]
            if values:
                result[column + "_mean_across_seed_summaries"] = statistics.mean(values)
                result[column + "_sd_across_seed_summaries"] = (
                    statistics.stdev(values) if len(values) > 1 else 0.0
                )
        summaries.append(result)
    aggregate_fields = list(dict.fromkeys(k for row in summaries for k in row))
    with (out_dir / "aggregate_timing.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=aggregate_fields)
        writer.writeheader()
        writer.writerows(summaries)
    return len(cell_files), len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path,
                        default=Path("AIO-mesh-submit-2/results/models"))
    parser.add_argument("--normalizer-dir", type=Path,
                        default=Path("results/rev1/p1_2_simulator/normalizers"))
    parser.add_argument("--data-path", type=Path, default=Path("data/real_telecom_combined.csv"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/rev1/p1_2_simulator/crossed_matrix"))
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    parser.add_argument("--topologies", nargs="+", choices=TOPOLOGIES, default=TOPOLOGIES)
    parser.add_argument("--occupancies", type=int, nargs="+", choices=OCCUPANCIES,
                        default=OCCUPANCIES)
    args = parser.parse_args()
    if args.steps < 1 or not args.seeds or len(set(args.seeds)) != len(args.seeds):
        raise SystemExit("steps must be positive and seeds must be unique/nonempty")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    models: dict[str, tuple[Path, Path]] = {}
    for topology in args.topologies:
        model = args.model_root / f"v11_{topology}" / f"dgrl_v11_final_{topology}.zip"
        normalizer = args.normalizer_dir / f"vec_normalize_v11_{topology}.pkl"
        if not model.is_file() or not normalizer.is_file():
            raise FileNotFoundError(f"missing pinned artifacts for {topology}: {model} {normalizer}")
        models[topology] = model, normalizer

    manifest_path = args.output_dir / "matrix_manifest.json"
    source_paths = [Path(__file__).resolve(), ROOT / "src/analytics/benchmark/benchmark_algorithm/run_load_sweep.py",
                    ROOT / "src/analytics/benchmark/benchmark_algorithm/algorithms.py",
                    ROOT / "src/analytics/benchmark/benchmark_algorithm/metrics.py",
                    ROOT / "src/orchestration/jo_vdpr/env.py", ROOT / "src/orchestration/jo_vdpr/topology.py"]
    manifest = {
        "protocol": "p1.2-crossed-synthetic-topology-occupancy-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "topologies": list(args.topologies), "occupancies_active_chains": list(args.occupancies),
        "seeds": args.seeds, "steps_per_seed": args.steps, "scenario": "bursty",
        "load_multiplier": 1.0, "policies": ["harp_protected", "saf_h_protected"],
        "background_chain_profile": {"cpu": 2.0, "ram": 2.0, "msd": 1,
                                      "bandwidth": 20.0, "placement": "round-robin"},
        "data_path": str(args.data_path), "data_sha256": sha256_file(args.data_path),
        "artifacts": {topo: {"model_path": str(model), "model_sha256": sha256_file(model),
                             "normalizer_pickle_path": str(norm),
                             "normalizer_pickle_sha256": sha256_file(norm),
                             "normalizer_npz_path": str(norm.with_suffix('.npz')),
                             "normalizer_npz_sha256": sha256_file(norm.with_suffix('.npz'))}
                      for topo, (model, norm) in models.items()},
        "source_sha256": {str(path.relative_to(ROOT)): sha256_file(path) for path in source_paths},
    }
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if existing:
        for key in ("topologies", "occupancies_active_chains", "seeds", "steps_per_seed",
                    "data_sha256", "artifacts", "source_sha256"):
            if existing.get(key) != manifest.get(key):
                raise RuntimeError(f"resume refused because manifest field changed: {key}")
        manifest = existing

    total = len(args.topologies) * len(args.occupancies) * len(args.seeds)
    completed = 0
    for topology in args.topologies:
        model, normalizer = models[topology]
        for occupancy in args.occupancies:
            cell_dir = args.output_dir / topology / f"chains_{occupancy}"
            cell_dir.mkdir(parents=True, exist_ok=True)
            for seed in args.seeds:
                seed_path = cell_dir / f"seed_{seed}.json"
                if seed_path.exists():
                    completed += 1
                    continue
                payload = run_cell_seed(topology, occupancy, seed, args, model, normalizer)
                atomic_json(seed_path, payload)
                completed += 1
                manifest["progress"] = {"cells_completed": completed, "cells_total": total,
                                         "last_cell": {"topology": topology,
                                                       "active_chains": occupancy,
                                                       "seed": seed}}
                atomic_json(manifest_path, manifest)
                print(f"completed {completed}/{total}: {topology} chains={occupancy} seed={seed}",
                      flush=True)
    cell_count, row_count = write_aggregates(args.output_dir)
    manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["result_cell_seed_files"] = cell_count
    manifest["per_seed_policy_rows"] = row_count
    atomic_json(manifest_path, manifest)
    print(json.dumps({"cells": cell_count, "rows": row_count,
                      "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
