from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

# Prevent PyTorch/OpenBLAS/MKL thread contention and deadlocks in linalg.qr on multi-core servers
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

from .algorithms import run_all_algorithms
from .config import (AlgorithmBenchmarkConfig, SCENARIO_CHOICES, TOPOLOGY_CHOICES,
                     load_params, scenario_jobs, topologies_for_selection)
from .env_factory import make_env
from .exporters import write_aggregate_summary, write_json, write_seed_summary, write_paired_statistics
from .metrics import RunMetrics
from .model_loader import build_model_from_policy_weights, load_normalizer
from src.analytics.benchmark.revision.provenance import sha256_file
from .plotting import plot_dashboard, plot_latency_cdf, plot_rolling_acceptance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline JO-VPPM algorithm benchmarks.")
    parser.add_argument("--topology", default="vietnam", choices=TOPOLOGY_CHOICES)
    parser.add_argument("--scenario", default="uniform", choices=SCENARIO_CHOICES)
    parser.add_argument("--load", default="stress", choices=["normal", "stress"])
    parser.add_argument("--version", default="v11")
    parser.add_argument("--steps", type=int, default=3000)
    seeds = parser.add_mutually_exclusive_group()
    seeds.add_argument("--single-seed", action="store_true")
    seeds.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--skip-exhaustive", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="Parallel seed workers per topology/scenario job.")
    parser.add_argument("--sla-scale", type=float, default=1.0, help="Multiply SLA thresholds; use <1 for stricter SLA.")
    parser.add_argument("--output-dir", default="results/benchmark_algorithm")
    parser.add_argument("--data-path", default="data/processed/real_telecom_combined.csv")
    parser.add_argument("--model-root", default="results/models")
    parser.add_argument("--model-path", type=Path, help="Pin a specific checkpoint for this run.")
    parser.add_argument("--normalizer-path", type=Path, help="Pin its matching VecNormalize artifact.")
    parser.add_argument("--ablation", action="store_true", help="Run HARP ablation study instead of baseline comparison.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.ablation:
        raise SystemExit(
            "The legacy --ablation path is retired because it evaluated an untrained no-GAT policy. "
            "Run the strict seven-variant evaluator instead: python -m src.analytics.ablation_study "
            "--topology <vietnam|nsfnet|geant2> --scenario <uniform|bursty|heavy_tail|chaos> "
            "--seeds 42 100 2024 8888 9999"
        )
    config = AlgorithmBenchmarkConfig(
        topology=args.topology,
        scenario=args.scenario,
        load=args.load,
        version=args.version,
        steps=args.steps,
        single_seed=args.single_seed,
        seed_override=tuple(args.seeds) if args.seeds is not None else None,
        skip_exhaustive=args.skip_exhaustive,
        workers=max(1, args.workers),
        sla_scale=args.sla_scale,
        output_dir=Path(args.output_dir),
        data_path=Path(args.data_path),
        model_root=Path(args.model_root),
        model_override=args.model_path,
        normalizer_override=args.normalizer_path,
    )
    is_ablation = False
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = config.output_dir / (f"ablation_{timestamp}" if is_ablation else timestamp)
    run_root.mkdir(parents=True, exist_ok=True)

    topologies = topologies_for_selection(config.topology)
    jobs = scenario_jobs(config.scenario if not is_ablation else "ablation", config.load)
    if not is_ablation:
        preflight_algorithm_inputs(config, topologies, jobs[0][1], jobs[0][2])
        write_run_manifest(run_root, config, topologies, jobs)

    # Determine the algorithm grouping keys based on mode
    if is_ablation:
        group_keys = ["harp_full", "harp_no_gat", "harp_no_hard_mask", "harp_soft_msd", "harp_no_adaptive"]
    else:
        group_keys = ["exhaustive_pair_search", "traditional_greedy", "saf_h", "decoupled_ai", "harp"]

    all_runs: List[RunMetrics] = []
    for topology in topologies:
        for display_scenario, env_scenario, job_load in jobs:
            print(f"Running topology={topology} scenario={display_scenario} env={env_scenario} load={job_load}")
            grouped: Dict[str, List[RunMetrics]] = {key: [] for key in group_keys}
            include_exhaustive = (
                not is_ablation and not config.skip_exhaustive
                and not (topology == "geant2" and config.steps > 1000)
                and not topology.startswith("synthetic_")
            )

            seed_results_list = run_seed_jobs(
                topology=topology,
                display_scenario=display_scenario,
                env_scenario=env_scenario,
                load=job_load,
                config=config,
                include_exhaustive=include_exhaustive,
                is_ablation=is_ablation,
            )
            expected_algorithms = expected_benchmark_algorithms(include_exhaustive)
            validate_benchmark_coverage(seed_results_list, config.seeds, config.steps, expected_algorithms)
            for seed, seed_results in seed_results_list:
                print(f"  seed={seed}")
                for algorithm, run in seed_results.items():
                    run.scenario = display_scenario
                    grouped.setdefault(algorithm, []).append(run)
                    all_runs.append(run)
                    print(
                        f"    {algorithm}: accept={run.acc_rate:.1f}% "
                        f"msd={run.msd_rate:.1f}% sla={run.sla_rate:.1f}% "
                        f"lat={run.avg_lat:.2f}ms reward={run.avg_reward:.1f}"
                    )

            combo_dir = run_root / f"{topology}_{display_scenario}_{job_load}"
            combo_dir.mkdir(parents=True, exist_ok=True)
            write_seed_summary(combo_dir / "seed_summary.csv", all_runs_for_group(grouped))
            write_aggregate_summary(combo_dir / "aggregate_summary.csv", grouped)
            write_json(combo_dir / "results.json", grouped)
            if not is_ablation:
                write_paired_statistics(combo_dir / "paired_statistics.json", all_runs_for_group(grouped))
            plot_dashboard(combo_dir, grouped)
            plot_latency_cdf(combo_dir, grouped)
            if len(config.seeds) > 1:
                plot_rolling_acceptance(combo_dir, grouped)

    write_seed_summary(run_root / "all_seed_summary.csv", all_runs)
    print(f"Saved algorithm benchmark outputs to {run_root}")


def preflight_algorithm_inputs(config, topologies, scenario, load):
    """Fail before any long run if data/model/normalizer/spaces are incompatible."""
    from .env_factory import resolve_data_path

    resolved_data = resolve_data_path(config.data_path)
    if not resolved_data.is_file():
        raise FileNotFoundError(f"Benchmark data is not a file: {resolved_data}")
    arrival_rate, ttl_range = load_params(load)
    for topology in topologies:
        model_path, norm_path = config.model_path(topology), config.norm_path(topology)
        if not model_path.is_file() or not norm_path.is_file():
            raise FileNotFoundError(
                f"Missing benchmark artifacts for {topology}: model={model_path}, normalizer={norm_path}"
            )
        env = make_env(
            topology, resolved_data, 2, arrival_rate, ttl_range, scenario, config.sla_scale
        )
        try:
            model = build_model_from_policy_weights(env, model_path)
            if model.observation_space != env.observation_space:
                raise ValueError(f"Observation-space mismatch for {topology}: {model_path}")
            if model.action_space != env.action_space:
                raise ValueError(f"Action-space mismatch for {topology}: {model_path}")
            normalizer = load_normalizer(norm_path, model.get_env())
            obs, _ = env.reset(seed=0)
            normalized = normalizer.normalize_obs(obs.reshape(1, -1).astype("float32"))
            if normalized.shape != (1, env.observation_space.shape[0]):
                raise ValueError(f"Normalizer dimension mismatch for {topology}: {norm_path}")
        finally:
            env.close()


def validate_benchmark_coverage(seed_results, expected_seeds, expected_steps, expected_algorithms):
    seeds = [seed for seed, _ in seed_results]
    if len(seeds) != len(set(seeds)) or set(seeds) != set(expected_seeds):
        raise RuntimeError(f"Benchmark seed coverage mismatch: expected={expected_seeds}, actual={seeds}")
    for seed, results in seed_results:
        if set(results) != set(expected_algorithms):
            raise RuntimeError(
                f"Benchmark policy coverage mismatch for seed={seed}: "
                f"expected={expected_algorithms}, actual={sorted(results)}"
            )
        hashes = set()
        for policy, metrics in results.items():
            summary = metrics.as_summary()
            if len(metrics.trace_records) != expected_steps:
                raise RuntimeError(f"Trace length mismatch for seed={seed}, policy={policy}")
            if metrics.requests <= 0:
                raise RuntimeError(f"No offered requests for seed={seed}, policy={policy}; cannot score run")
            if not summary.get("trace_sha256"):
                raise RuntimeError(f"Missing offered-trace hash for seed={seed}, policy={policy}")
            hashes.add(summary["trace_sha256"])
        if len(hashes) != 1:
            raise RuntimeError(f"Policies received different offered traces for seed={seed}: {sorted(hashes)}")


def expected_benchmark_algorithms(include_exhaustive: bool) -> list[str]:
    policies = ("traditional_greedy", "saf_h", "decoupled_ai", "harp")
    expected = [f"{policy}_{mode}" for mode in ("protected", "unprotected") for policy in policies]
    if include_exhaustive:
        expected.extend(f"exhaustive_pair_search_{mode}" for mode in ("protected", "unprotected"))
    return expected


def write_run_manifest(run_root, config, topologies, jobs):
    from importlib.metadata import PackageNotFoundError, version
    from .env_factory import resolve_data_path

    data_file = resolve_data_path(config.data_path)
    artifacts = {}
    topology_metadata = {}
    for topology in topologies:
        from src.orchestration.jo_vdpr.topology import TopologyManager

        topology_manager = TopologyManager(topology)
        topology_metadata[topology] = {
            "description": topology_manager.description,
            "num_nodes": topology_manager.num_nodes,
            "undirected_adjacency_edges": int((topology_manager.adj_matrix.sum() - topology_manager.num_nodes) / 2),
            "synthetic": topology_manager.is_synthetic,
        }
        model, normalizer = config.model_path(topology), config.norm_path(topology)
        artifacts[topology] = {
            "model_path": str(model), "model_sha256": sha256_file(model),
            "normalizer_path": str(normalizer), "normalizer_sha256": sha256_file(normalizer),
        }
    modules = [
        Path(__file__), Path(__file__).with_name("algorithms.py"),
        Path(__file__).with_name("metrics.py"), Path(__file__).with_name("model_loader.py"),
        Path(__file__).parents[3] / "orchestration/jo_vdpr/env.py",
        Path(__file__).parents[3] / "orchestration/jo_vdpr/topology.py",
    ]
    deps = {}
    for package in ("numpy", "torch", "stable-baselines3", "sb3-contrib", "gymnasium"):
        try:
            deps[package] = version(package)
        except PackageNotFoundError:
            deps[package] = None
    payload = {
        "protocol": "benchmark-v2", "topologies": topologies,
        "topology_metadata": topology_metadata,
        "scenario_jobs": jobs, "seeds": config.seeds, "steps": config.steps,
        "load": config.load, "sla_scale": config.sla_scale,
        "data_path": str(data_file), "data_sha256": sha256_file(data_file),
        "artifacts": artifacts,
        "source_sha256": {str(path): sha256_file(path) for path in modules},
        "dependencies": deps,
        "chaos_profile": {
            "calm_to_stress": 0.08, "stress_to_calm": 0.35,
            "cpu_multiplier": 2.5, "ram_multiplier": 1.75, "sid_increment": 2,
        },
    }
    (run_root / "run_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_seed_jobs(
    topology: str,
    display_scenario: str,
    env_scenario: str,
    load: str,
    config: AlgorithmBenchmarkConfig,
    include_exhaustive: bool,
    is_ablation: bool = False,
) -> List[tuple[int, Dict[str, RunMetrics]]]:
    if config.workers <= 1 or len(config.seeds) <= 1:
        return [
            (
                seed,
                run_one_seed(
                    topology,
                    display_scenario,
                    env_scenario,
                    load,
                    config.steps,
                    seed,
                    config.data_path,
                    config.model_path(topology),
                    config.norm_path(topology),
                    include_exhaustive,
                    config.sla_scale,
                    is_ablation=is_ablation,
                ),
            )
            for seed in config.seeds
        ]

    results: List[tuple[int, Dict[str, RunMetrics]]] = []
    with ProcessPoolExecutor(max_workers=config.workers) as executor:
        futures = {
            executor.submit(
                run_one_seed,
                topology,
                display_scenario,
                env_scenario,
                load,
                config.steps,
                seed,
                config.data_path,
                config.model_path(topology),
                config.norm_path(topology),
                include_exhaustive,
                config.sla_scale,
                is_ablation,
            ): seed
            for seed in config.seeds
        }
        for future in as_completed(futures):
            results.append((futures[future], future.result()))
    return sorted(results, key=lambda item: item[0])


def run_one_seed(
    topology: str,
    display_scenario: str,
    env_scenario: str,
    load: str,
    steps: int,
    seed: int,
    data_path: Path,
    model_path: Path,
    norm_path: Path,
    include_exhaustive: bool,
    sla_scale: float,
    is_ablation: bool = False,
) -> Dict[str, RunMetrics]:
    arrival_rate, ttl_range = load_params(load)

    def make_env_fn():
        return make_env(
            topology_name=topology,
            data_path=data_path,
            steps=steps,
            arrival_rate=arrival_rate,
            ttl_range=ttl_range,
            scenario=env_scenario,
            sla_scale=sla_scale,
        )

    if is_ablation:
        return run_all_ablation_algorithms(
            make_env_fn=make_env_fn,
            scenario=env_scenario,
            steps=steps,
            seed=seed,
            model_path=model_path,
            norm_path=norm_path,
        )

    return run_all_algorithms(
        make_env_fn=make_env_fn,
        scenario=env_scenario,
        steps=steps,
        seed=seed,
        model_path=model_path,
        norm_path=norm_path,
        include_exhaustive=include_exhaustive,
    )


def all_runs_for_group(grouped: Dict[str, List[RunMetrics]]) -> List[RunMetrics]:
    rows: List[RunMetrics] = []
    for runs in grouped.values():
        rows.extend(runs)
    return rows


if __name__ == "__main__":
    main()
