"""Run the constrained pair-level CSPF baseline on the paper's stress protocol."""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.analytics.benchmark.benchmark_algorithm.algorithms import run_cspf
from src.analytics.benchmark.benchmark_algorithm.config import (
    REAL_TOPOLOGIES, load_params, scenario_jobs,
)
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env, resolve_data_path
from src.analytics.benchmark.revision.provenance import sha256_file
from src.orchestration.jo_vdpr import env as env_module, topology as topology_module


SEEDS = (42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
         11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192)
SCENARIOS = ("elephant_stress", "burst_surge", "chaos")


def main() -> None:
    data = resolve_data_path(Path("data/real_telecom_combined.csv"))
    steps = 3000
    rows = []
    for topology in REAL_TOPOLOGIES:
        for display, traffic, load in (job for name in SCENARIOS for job in scenario_jobs(name, "stress")):
            arrival, ttl_range = load_params(load)
            factory = lambda t=topology, a=arrival, ttl=ttl_range, s=traffic: make_env(
                t, data, steps, a, ttl, s
            )
            for seed in SEEDS:
                metrics = run_cspf(factory, traffic, steps, seed, protected=True)
                row = metrics.as_summary()
                row["scenario"] = display
                rows.append(row)
                print(f"{topology} {display} seed={seed}: accept={metrics.acc_rate:.3f}%", flush=True)

    output = Path("results/rev1/cspf_baseline")
    output.mkdir(parents=True, exist_ok=True)
    with (output / "cspf_per_seed.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)
    groups = {}
    for row in rows:
        key = (row["topology"], row["scenario"])
        groups.setdefault(key, []).append(row)
    summary = []
    for (topology, scenario), group in groups.items():
        summary.append({
            "topology": topology, "scenario": scenario, "seeds": len(group),
            "acceptance_mean": sum(float(r["acceptance_rate"]) for r in group) / len(group),
            "acceptance_population_sd": statistics.pstdev(float(r["acceptance_rate"]) for r in group),
            "safe_acceptance_mean": sum(float(r["safe_acceptance_rate"]) for r in group) / len(group),
            "safe_acceptance_population_sd": statistics.pstdev(float(r["safe_acceptance_rate"]) for r in group),
            "admitted_hard_violation_mean": sum(float(r["admitted_hard_violation_rate"]) for r in group) / len(group),
        })
    with (output / "cspf_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    manifest = {
        "protocol": "cspf-pair-baseline-v1", "topologies": REAL_TOPOLOGIES,
        "scenarios": SCENARIOS, "seeds": SEEDS, "steps_per_seed_condition": steps,
        "protected_admission": True, "candidate_objective": ["minimum topology latency", "minimum hop count", "minimum placement CPU utilization"],
        "action_scope": "distinct placement/routing endpoint pair; no ingress/egress source-destination request exists",
        "data_path": str(data), "data_sha256": sha256_file(data),
        "source_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(Path(__file__).resolve().parents[2] / "src/analytics/benchmark/benchmark_algorithm/algorithms.py"):
                sha256_file(Path(__file__).resolve().parents[2] / "src/analytics/benchmark/benchmark_algorithm/algorithms.py"),
            str(Path(env_module.__file__)): sha256_file(Path(env_module.__file__)),
            str(Path(topology_module.__file__)): sha256_file(Path(topology_module.__file__)),
        },
    }
    (output / "cspf_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved {len(rows)} CSPF rows under {output}", flush=True)


if __name__ == "__main__":
    main()
