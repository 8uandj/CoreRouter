from __future__ import annotations

import argparse
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
from .ablation_algorithms import run_all_ablation_algorithms
from .config import AlgorithmBenchmarkConfig, SCENARIO_CHOICES, load_params, scenario_jobs
from .env_factory import make_env
from .exporters import write_aggregate_summary, write_json, write_seed_summary
from .metrics import RunMetrics
from .plotting import plot_dashboard, plot_latency_cdf, plot_rolling_acceptance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline JO-VPPM algorithm benchmarks.")
    parser.add_argument("--topology", default="vietnam", choices=["vietnam", "nsfnet", "geant2", "all"])
    parser.add_argument("--scenario", default="uniform", choices=SCENARIO_CHOICES)
    parser.add_argument("--load", default="stress", choices=["normal", "stress"])
    parser.add_argument("--version", default="v11")
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--single-seed", action="store_true")
    parser.add_argument("--skip-exhaustive", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="Parallel seed workers per topology/scenario job.")
    parser.add_argument("--sla-scale", type=float, default=1.0, help="Multiply SLA thresholds; use <1 for stricter SLA.")
    parser.add_argument("--output-dir", default="results/benchmark_algorithm")
    parser.add_argument("--data-path", default="data/processed/real_telecom_combined.csv")
    parser.add_argument("--model-root", default="results/models")
    parser.add_argument("--ablation", action="store_true", help="Run HARP ablation study instead of baseline comparison.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AlgorithmBenchmarkConfig(
        topology=args.topology,
        scenario=args.scenario,
        load=args.load,
        version=args.version,
        steps=args.steps,
        single_seed=args.single_seed,
        skip_exhaustive=args.skip_exhaustive,
        workers=max(1, args.workers),
        sla_scale=args.sla_scale,
        output_dir=Path(args.output_dir),
        data_path=Path(args.data_path),
        model_root=Path(args.model_root),
    )
    is_ablation = args.ablation
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = config.output_dir / (f"ablation_{timestamp}" if is_ablation else timestamp)
    run_root.mkdir(parents=True, exist_ok=True)

    topologies = ["vietnam", "nsfnet", "geant2"] if config.topology == "all" else [config.topology]
    jobs = scenario_jobs(config.scenario if not is_ablation else "ablation", config.load)

    # Determine the algorithm grouping keys based on mode
    if is_ablation:
        group_keys = ["harp_full", "harp_no_gat", "harp_no_hard_mask", "harp_soft_msd", "harp_no_adaptive"]
    else:
        group_keys = ["exhaustive_pair_search", "traditional_greedy", "decoupled_ai", "jo_vppm"]

    all_runs: List[RunMetrics] = []
    for topology in topologies:
        for display_scenario, env_scenario, job_load in jobs:
            print(f"Running topology={topology} scenario={display_scenario} env={env_scenario} load={job_load}")
            grouped: Dict[str, List[RunMetrics]] = {key: [] for key in group_keys}
            include_exhaustive = not is_ablation and not config.skip_exhaustive and not (topology == "geant2" and config.steps > 1000)

            seed_results_list = run_seed_jobs(
                topology=topology,
                display_scenario=display_scenario,
                env_scenario=env_scenario,
                load=job_load,
                config=config,
                include_exhaustive=include_exhaustive,
                is_ablation=is_ablation,
            )
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
            plot_dashboard(combo_dir, grouped)
            plot_latency_cdf(combo_dir, grouped)
            if len(config.seeds) > 1:
                plot_rolling_acceptance(combo_dir, grouped)

    write_seed_summary(run_root / "all_seed_summary.csv", all_runs)
    print(f"Saved algorithm benchmark outputs to {run_root}")


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
