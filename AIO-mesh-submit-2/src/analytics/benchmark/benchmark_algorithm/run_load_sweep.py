"""Matched multi-policy offered-load sweep for the offline Gym environment."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .algorithms import run_all_algorithms
from .config import AlgorithmBenchmarkConfig, TOPOLOGY_CHOICES, topologies_for_selection
from .run_all import preflight_algorithm_inputs
from src.analytics.benchmark.revision.provenance import sha256_file
from src.analytics.benchmark.revision.statistics import paired_statistics
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env, resolve_data_path


LOADS = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5]
POLICIES = [f"{policy}_{mode}" for mode in ("protected", "unprotected")
            for policy in ("harp", "saf_h", "cspf", "traditional_greedy", "decoupled_ai")]


def _seed_active_chains(env, count: int, chain_cpu: float = 2.0, chain_ram: float = 2.0,
                        chain_bandwidth: float = 20.0) -> None:
    """Install a deterministic background-chain population after each reset."""
    if count < 0:
        raise ValueError("active chain count must be non-negative")
    if count and (chain_cpu <= 0 or chain_ram <= 0 or chain_bandwidth <= 0):
        raise ValueError("background chain resource demands must be positive")
    n = env.num_nodes
    max_per_node = min(int(env.max_cpu // chain_cpu), int(env.max_ram // chain_ram))
    if count > n * max_per_node:
        raise ValueError(
            f"{count} active chains exceed per-node CPU/RAM capacity for {n} nodes "
            f"({max_per_node} chains per node at the configured profile)"
        )
    for index in range(count):
        placement = index % n
        routing = (index + 1) % n
        env._state[placement * 3] += chain_cpu
        env._state[placement * 3 + 1] += chain_ram
        env._state[routing * 3 + 2] = max(env._state[routing * 3 + 2], 1.0)
        if placement != routing:
            env._link_bw[placement, routing] -= chain_bandwidth
            env._link_bw[routing, placement] -= chain_bandwidth
        env.active_flows.append({
            "placement_node": placement, "routing_node": routing,
            "cpu_allocated": chain_cpu, "ram_allocated": chain_ram,
            "msd_allocated": 1, "bw": chain_bandwidth,
            "ttl": max(env.EPISODE_LEN * 2 + 1, 2),
        })


def build_env_factory(topology: str, data_path: Path, steps: int, load: float,
                      active_chains: int = 0):
    topo_scale = {"vietnam": 1.0, "nsfnet": 1.4, "geant2": 2.3,
                  "synthetic_25": 2.5, "synthetic_50": 5.0, "synthetic_100": 10.0}[topology]
    base_ttl = (max(5, int(15 * topo_scale)), max(20, int(60 * topo_scale)))
    arrival_rate = min(1.0, load)
    ttl_range = (int(base_ttl[0] * max(1.0, load)), int(base_ttl[1] * max(1.0, load)))

    def make_env_fn():
        env = make_env(topology, data_path, steps, arrival_rate, ttl_range, "bursty")
        if active_chains:
            original_reset = env.reset

            def reset_with_background(*args, **kwargs):
                _, info = original_reset(*args, **kwargs)
                _seed_active_chains(env, active_chains)
                return env._get_obs(), info

            env.reset = reset_with_background
        if load > 1.0:
            original_loader = env._load_request_for_step

            def scaled_loader(step):
                original_loader(step)
                req = env._current_req
                env._current_req = {
                    **req,
                    "cpu": min(env.max_cpu * 0.9, float(req["cpu"]) * load),
                    "ram": min(env.max_ram * 0.9, float(req["ram"]) * load),
                    "msd": min(int(env.node_msd_limits.max()) - 1,
                               int(req["msd"]) * max(1, round(load))),
                }

            env._load_request_for_step = scaled_loader
        return env

    return make_env_fn


def bootstrap_mean_ci(values: list[float], seed: int, n_boot: int = 10_000):
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Cannot aggregate empty or non-finite seed values")
    if np.all(array == array[0]):
        return float(array.mean()), float(array[0]), float(array[0])
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(n_boot, len(array)), replace=True).mean(axis=1)
    lo, hi = np.quantile(samples, [0.025, 0.975])
    return float(array.mean()), float(lo), float(hi)


def run_sweep(topology, loads, steps, seeds, data_path, model_path, norm_path,
              active_chains: int = 0):
    """Return rows per method/load/seed; all methods see replay-matched traces."""
    rows = []
    for load in loads:
        factory = build_env_factory(topology, data_path, steps, load, active_chains)
        for seed in seeds:
            results = run_all_algorithms(
                make_env_fn=factory, scenario="bursty", steps=steps, seed=seed,
                model_path=model_path, norm_path=norm_path, include_exhaustive=False,
            )
            for algorithm, metrics in results.items():
                row = metrics.as_summary()
                row.update({"load_multiplier": float(load), "scenario": f"load_{load:.1f}",
                            "initial_active_chains": int(active_chains)})
                rows.append(row)
    return rows


def write_outputs(rows, out_dir: Path, topology: str, data_path: Path, model_path: Path,
                  norm_path: Path, seeds, steps, active_chains: int = 0):
    out_dir.mkdir(parents=True, exist_ok=True)
    zero_offered = [row for row in rows if int(row["requests"]) == 0]
    if zero_offered:
        raise RuntimeError(
            "Load-sweep run with zero offered arrivals cannot be treated as 0% acceptance; "
            f"increase steps or change seeds. Affected rows: {zero_offered}"
        )
    seed_csv = out_dir / f"{topology}_load_sweep_per_seed.csv"
    if not rows:
        raise RuntimeError("Load sweep produced no rows")
    seed_fields = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with seed_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=seed_fields)
        writer.writeheader()
        writer.writerows(rows)

    paired = []
    for load in sorted({row["load_multiplier"] for row in rows}):
        load_rows = [row for row in rows if row["load_multiplier"] == load]
        paired.extend(paired_statistics(load_rows, {
            "metric": "safe_acceptance_rate",
            "comparisons": [{"name": "harp_vs_saf_h_protected", "treatment": "harp_protected", "control": "saf_h_protected"}],
            "n_bootstrap": 10_000, "analysis_seed": 20261116,
        }))
        paired[-1]["load_multiplier"] = load
        paired[-1]["topology"] = topology
    (out_dir / f"{topology}_load_sweep_paired.json").write_text(json.dumps(paired, indent=2), encoding="utf-8")

    aggregates = []
    for load in sorted({row["load_multiplier"] for row in rows}):
        for policy in POLICIES:
            group = [row for row in rows if row["load_multiplier"] == load and row["algorithm"] == policy]
            if not group:
                raise RuntimeError(f"Missing load-sweep rows: topology={topology}, load={load}, policy={policy}")
            mean, low, high = bootstrap_mean_ci([float(row["safe_acceptance_rate"]) for row in group], 20261116)
            violation, vlow, vhigh = bootstrap_mean_ci([float(row["msd_violation_rate"]) for row in group], 20261116)
            aggregates.append({"topology": topology, "load_multiplier": load, "algorithm": policy,
                               "seeds": len(group), "safe_acceptance_mean": mean,
                               "safe_acceptance_ci95_low": low, "safe_acceptance_ci95_high": high,
                               "admitted_msd_violation_mean": violation,
                               "admitted_msd_ci95_low": vlow, "admitted_msd_ci95_high": vhigh})
    agg_csv = out_dir / f"{topology}_load_sweep_aggregate.csv"
    with agg_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregates[0]))
        writer.writeheader()
        writer.writerows(aggregates)

    manifest = {
        "protocol": "protected-load-sweep-v2", "topology": topology, "loads": LOADS,
        "initial_active_chains": active_chains,
        "background_chain_profile": {"cpu": 2.0, "ram": 2.0, "msd": 1, "bandwidth": 20.0,
                                      "ttl_steps": "2 * episode length + 1", "placement": "round-robin"},
        "seeds": seeds, "steps": steps, "policies": POLICIES,
        "data_path": str(data_path), "data_sha256": sha256_file(data_path),
        "model_path": str(model_path), "model_sha256": sha256_file(model_path),
        "normalizer_path": str(norm_path), "normalizer_sha256": sha256_file(norm_path),
        "source_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(Path(__file__).with_name("algorithms.py")): sha256_file(Path(__file__).with_name("algorithms.py")),
            str(Path(__file__).with_name("config.py")): sha256_file(Path(__file__).with_name("config.py")),
            str(Path(__file__).parents[3] / "orchestration/jo_vdpr/env.py"): sha256_file(
                Path(__file__).parents[3] / "orchestration/jo_vdpr/env.py"),
            str(Path(__file__).parents[3] / "orchestration/jo_vdpr/topology.py"): sha256_file(
                Path(__file__).parents[3] / "orchestration/jo_vdpr/topology.py"),
        },
        "ttl_topology_scale": {"vietnam": 1.0, "nsfnet": 1.4, "geant2": 2.3,
                                "synthetic_25": 2.5, "synthetic_50": 5.0, "synthetic_100": 10.0},
        "overload_demand_scaling": "CPU/RAM multiplied by load (capped at 90%); SID depth scaled by rounded load",
    }
    (out_dir / f"{topology}_load_sweep_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return aggregates


def plot_load_sweep(aggregates, out_path: Path, topology: str):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    styles = {"harp_protected": "o-", "saf_h_protected": "s-",
              "cspf_protected": "P-",
              "traditional_greedy_protected": "^-", "decoupled_ai_protected": "d-",
              "harp_unprotected": "o--", "saf_h_unprotected": "s--", "cspf_unprotected": "P--",
              "traditional_greedy_unprotected": "^--", "decoupled_ai_unprotected": "d--"}
    for policy in POLICIES:
        group = sorted((r for r in aggregates if r["algorithm"] == policy), key=lambda x: x["load_multiplier"])
        x = [r["load_multiplier"] for r in group]
        axes[0].plot(x, [r["safe_acceptance_mean"] for r in group], styles[policy], label=policy)
        axes[0].fill_between(x, [r["safe_acceptance_ci95_low"] for r in group],
                             [r["safe_acceptance_ci95_high"] for r in group], alpha=0.12)
        axes[1].plot(x, [r["admitted_msd_violation_mean"] for r in group], styles[policy], label=policy)
    axes[0].set_ylabel("Acceptance among offered requests (%)")
    axes[1].set_ylabel("Admitted MSD violation rate (%)")
    for ax in axes:
        ax.set_xlabel("Offered load multiplier")
        ax.set_xticks(LOADS)
        ax.grid(True, linestyle="--", alpha=0.4)
    axes[0].set_ylim(0, 105)
    axes[1].legend(fontsize=8)
    fig.suptitle(f"Protected baseline load sweep: {topology}")
    fig.tight_layout()
    fig.savefig(out_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Matched protected-policy load sweep")
    parser.add_argument("--topology", default="vietnam", choices=TOPOLOGY_CHOICES)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718])
    parser.add_argument("--output-dir", default="results/benchmark_algorithm/load_sweep")
    parser.add_argument("--data-path", default="data/processed/real_telecom_combined.csv")
    parser.add_argument("--model-root", default="results/models")
    parser.add_argument("--version", default="v11")
    parser.add_argument("--model-path", type=Path, help="Pin a specific N²-action policy checkpoint.")
    parser.add_argument("--normalizer-path", type=Path, help="Pin its matching VecNormalize artifact.")
    parser.add_argument("--active-chains", type=int, default=0,
                        help="Seed this many deterministic background chains before each matched trace.")
    args = parser.parse_args()
    topologies = topologies_for_selection(args.topology)
    data_path = resolve_data_path(Path(args.data_path))
    config = AlgorithmBenchmarkConfig(version=args.version, data_path=data_path, model_root=Path(args.model_root),
                                      model_override=args.model_path, normalizer_override=args.normalizer_path)
    for topology in topologies:
        model, normalizer = config.model_path(topology), config.norm_path(topology)
        preflight_algorithm_inputs(config, [topology], "bursty", "stress")
        rows = run_sweep(topology, LOADS, args.steps, args.seeds, data_path, model, normalizer,
                         active_chains=args.active_chains)
        aggregate = write_outputs(rows, Path(args.output_dir), topology, data_path, model,
                                  normalizer, args.seeds, args.steps, active_chains=args.active_chains)
        plot_load_sweep(aggregate, Path(args.output_dir) / f"{topology}_load_sweep.pdf", topology)


if __name__ == "__main__":
    main()
