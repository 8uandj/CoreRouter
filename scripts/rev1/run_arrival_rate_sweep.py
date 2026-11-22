"""Matched arrival-rate-only sweep; request profile and TTL stay fixed."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.analytics.benchmark.benchmark_algorithm.algorithms import run_all_algorithms
from src.analytics.benchmark.benchmark_algorithm.config import AlgorithmBenchmarkConfig, REAL_TOPOLOGIES
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env, resolve_data_path
from src.analytics.benchmark.benchmark_algorithm.run_all import preflight_algorithm_inputs
from src.analytics.benchmark.revision.provenance import sha256_file
from src.orchestration.jo_vdpr import env as env_module, topology as topology_module
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ARRIVAL_RATES = (0.2, 0.4, 0.6, 0.8, 1.0)
SCENARIO = "bursty"
TTL_RANGE = (100, 500)
PAPER_SEEDS = (42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
               11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", choices=(*REAL_TOPOLOGIES, "all"), default="all")
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--seeds", type=int, nargs="+", default=PAPER_SEEDS)
    parser.add_argument("--data-path", type=Path, default=Path("data/real_telecom_combined.csv"))
    parser.add_argument("--model-root", type=Path, default=None,
                        help="Optional legacy layout root; by default use corrected N-squared retrains")
    parser.add_argument("--corrected-root", type=Path,
                        default=Path("results/models/retrain_v11_20261119_corrected"))
    parser.add_argument("--version", default="v11")
    parser.add_argument("--output-dir", type=Path, default=Path("results/rev1/arrival_rate_sweep"))
    args = parser.parse_args()
    topologies = list(REAL_TOPOLOGIES) if args.topology == "all" else [args.topology]
    data = resolve_data_path(args.data_path)
    configs = {}
    # Check policy artifacts and spaces once per topology before the full sweep.
    for topology in topologies:
        if args.model_root is None:
            base = args.corrected_root / topology
            config = AlgorithmBenchmarkConfig(
                data_path=data,
                model_override=base / f"dgrl_v11_final_{topology}.zip",
                normalizer_override=base / f"vec_normalize_v11_{topology}.pkl",
            )
        else:
            config = AlgorithmBenchmarkConfig(data_path=data, model_root=args.model_root,
                                              version=args.version)
        preflight_algorithm_inputs(config, [topology], SCENARIO, "stress")
        configs[topology] = config

    rows = []
    for topology in topologies:
        config = configs[topology]
        model, normalizer = config.model_path(topology), config.norm_path(topology)
        for rate in ARRIVAL_RATES:
            factory = lambda t=topology, r=rate: make_env(
                t, data, args.steps, r, TTL_RANGE, SCENARIO
            )
            for seed in args.seeds:
                runs = run_all_algorithms(
                    factory, SCENARIO, args.steps, seed, model, normalizer,
                    include_exhaustive=False, include_unprotected=False,
                )
                for policy, metrics in runs.items():
                    row = metrics.as_summary()
                    row.update({"arrival_rate": rate, "fixed_ttl_min": TTL_RANGE[0],
                                "fixed_ttl_max": TTL_RANGE[1], "scenario": SCENARIO})
                    rows.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "arrival_rate_per_seed.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)
    aggregates = []
    for topology in topologies:
        for rate in ARRIVAL_RATES:
            for policy in manifest_policies():
                group = [r for r in rows if r["topology"] == topology and
                         r["arrival_rate"] == rate and r["algorithm"] == policy]
                values = np.asarray([float(r["safe_acceptance_rate"]) for r in group], dtype=float)
                if len(values) != len(args.seeds):
                    raise RuntimeError(f"Seed coverage mismatch for {topology}/{rate}/{policy}: {len(values)}")
                rng = np.random.default_rng(20261118)
                boot = rng.choice(values, size=(10_000, len(values)), replace=True).mean(axis=1)
                lo, hi = np.quantile(boot, [0.025, 0.975])
                aggregates.append({"topology": topology, "arrival_rate": rate, "algorithm": policy,
                                   "seeds": len(values), "safe_acceptance_mean": float(values.mean()),
                                   "safe_acceptance_sd": float(values.std(ddof=1)),
                                   "safe_acceptance_ci95_low": float(lo),
                                   "safe_acceptance_ci95_high": float(hi)})
    with (args.output_dir / "arrival_rate_aggregate.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregates[0]))
        writer.writeheader()
        writer.writerows(aggregates)
    fig, axes = plt.subplots(1, len(topologies), figsize=(5.0 * len(topologies), 3.6), sharey=True)
    if len(topologies) == 1:
        axes = [axes]
    labels = {"harp_protected": "HARP", "saf_h_protected": "SAF-H",
              "cspf_protected": "CSPF", "traditional_greedy_protected": "Greedy",
              "decoupled_ai_protected": "Decoupled AI"}
    for ax, topology in zip(axes, topologies):
        for policy in manifest_policies():
            group = sorted((r for r in aggregates if r["topology"] == topology and r["algorithm"] == policy),
                           key=lambda r: r["arrival_rate"])
            x = [r["arrival_rate"] for r in group]
            y = [r["safe_acceptance_mean"] for r in group]
            ax.plot(x, y, marker="o", label=labels[policy])
            ax.fill_between(x, [r["safe_acceptance_ci95_low"] for r in group],
                            [r["safe_acceptance_ci95_high"] for r in group], alpha=0.12)
        ax.set_title(topology.upper())
        ax.set_xlabel("Request arrival probability")
        ax.set_xticks(ARRIVAL_RATES)
        ax.set_ylim(0, 100)
        ax.grid(True, linestyle="--", alpha=0.35)
    axes[0].set_ylabel("Safe acceptance among offered requests (%)")
    axes[-1].legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(args.output_dir / "arrival_rate_only.pdf", bbox_inches="tight")
    plt.close(fig)
    manifest = {
        "protocol": "arrival-rate-only-v1", "topologies": topologies,
        "scenario": SCENARIO, "arrival_rates": ARRIVAL_RATES,
        "fixed_ttl_range": TTL_RANGE, "steps_per_seed_condition": args.steps,
        "seeds": args.seeds,
        "policies": manifest_policies(),
        "request_cpu_ram_msd_profile": "unchanged; source data and bursty scenario are fixed",
        "data_path": str(data), "data_sha256": sha256_file(data),
        "models": {topology: {"checkpoint": str(configs[topology].model_path(topology)),
                              "checkpoint_sha256": sha256_file(configs[topology].model_path(topology)),
                              "normalizer": str(configs[topology].norm_path(topology)),
                              "normalizer_sha256": sha256_file(configs[topology].norm_path(topology))}
                   for topology in topologies},
        "source_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(Path(__file__).resolve().parents[2] / "src/analytics/benchmark/benchmark_algorithm/algorithms.py"):
                sha256_file(Path(__file__).resolve().parents[2] / "src/analytics/benchmark/benchmark_algorithm/algorithms.py"),
            str(Path(env_module.__file__)): sha256_file(Path(env_module.__file__)),
            str(Path(topology_module.__file__)): sha256_file(Path(topology_module.__file__)),
        },
    }
    (args.output_dir / "arrival_rate_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved {len(rows)} matched seed-policy rows to {path}", flush=True)


def manifest_policies():
    return ["harp_protected", "saf_h_protected", "cspf_protected",
            "traditional_greedy_protected", "decoupled_ai_protected"]


if __name__ == "__main__":
    main()
