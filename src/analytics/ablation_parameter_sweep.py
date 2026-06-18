"""
HARP ablation and parameter sensitivity sweep runner.

This script runs the integrated architectural ablation study and operational
parameter sensitivity sweeps. It sweeps SLA latency thresholds and migration
warning thresholds on trained ablation models, generating trade-off curves.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analytics.benchmark.benchmark_algorithm.model_loader import (
    build_model_from_policy_weights,
    load_normalizer,
    normalized_obs,
)
from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import TopologyManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("harp-parameter-sweep")


@dataclass(frozen=True)
class Variant:
    key: str
    name: str
    hypothesis: str
    model_key: Optional[str] = None
    policy: str = "harp"
    use_gat_model: bool = True
    use_hard_mask: bool = True
    enforce_msd_constraint: bool = True
    soft_msd_penalty: bool = False
    adaptive_penalty: bool = True


VARIANTS: List[Variant] = [
    Variant(
        key="harp_full",
        name="HARP full",
        hypothesis="Full hardware-aware GAT policy with hard safety and adaptive SLA/migration penalties.",
    ),
    Variant(
        key="harp_wo_gat",
        name="HARP w/o GAT",
        hypothesis="Topology encoder contribution: replace GAT with a flat MLP policy.",
    ),
    Variant(
        key="harp_wo_hard_masking",
        name="HARP w/o hard masking",
        hypothesis="Safety masking contribution: allow policy sampling over unsafe actions, then rely on admission rejection.",
        use_hard_mask=False,
    ),
    Variant(
        key="harp_wo_mask_unchecked",
        model_key="harp_wo_hard_masking",
        name="HARP w/o mask + unchecked admission",
        hypothesis="Two-layer safety contribution: allow unmasked policy outputs to bypass MSD admission validation.",
        use_hard_mask=False,
        enforce_msd_constraint=False,
    ),
    Variant(
        key="harp_soft_msd_penalty",
        name="HARP with soft MSD penalty",
        hypothesis="Hard constraint versus reward penalty: allow MSD-unsafe admissions and penalize them softly.",
        use_hard_mask=False,
        enforce_msd_constraint=False,
        soft_msd_penalty=True,
    ),
    Variant(
        key="harp_wo_adaptive_penalty",
        name="HARP w/o adaptive penalty",
        hypothesis="SLA/migration penalty contribution: disable adaptive SLA, switching, and evacuation penalties.",
        adaptive_penalty=False,
    ),
]


def resolve_data_path(path: Path) -> Path:
    if path.exists():
        return path
    fallback = Path("data/real_telecom_combined.csv")
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Cannot find data file: {path}")


def resolve_variant_model_paths(
    model_root: Path,
    version: str,
    topology: str,
    variant: Variant,
) -> tuple[Path, Path, str]:
    checkpoint_key = variant.model_key or variant.key
    variant_roots = [
        model_root / "ablation" / checkpoint_key,
        model_root / version / "ablation" / checkpoint_key,
        model_root / checkpoint_key,
    ]
    model_names = [
        f"{checkpoint_key}_{topology}.zip",
        f"dgrl_{version}_{checkpoint_key}_{topology}.zip",
        f"dgrl_{version}_final_{checkpoint_key}_{topology}.zip",
    ]
    norm_names = [
        f"{checkpoint_key}_vec_normalize_{topology}.pkl",
        f"vec_normalize_{version}_{checkpoint_key}_{topology}.pkl",
    ]

    for root in variant_roots:
        model = next((root / name for name in model_names if (root / name).exists()), None)
        norm = next((root / name for name in norm_names if (root / name).exists()), None)
        if model is not None and norm is not None:
            source = f"variant_checkpoint:{model}"
            return model, norm, source

    searched = "\n".join(str(root) for root in variant_roots)
    raise FileNotFoundError(
        f"Missing strict ablation checkpoint for {variant.key} on topology={topology}.\n"
        f"Checkpoint key searched: {checkpoint_key}\n"
        f"Expected one model and one variant VecNormalize file under:\n{searched}"
    )


def make_env(
    variant: Variant,
    topology: str,
    data_path: Path,
    steps: int,
    scenario: str,
) -> JOVDPREnv:
    reward = RewardCalculator(
        lambda_latency=-50.0 if variant.adaptive_penalty else 0.0,
        switching_cost=-10.0 if variant.adaptive_penalty else 0.0,
        evacuation_penalty=-50.0 if variant.adaptive_penalty else 0.0,
        msd_violation_penalty=-50.0 if variant.soft_msd_penalty else 0.0,
    )
    env = JOVDPREnv(
        repository=CSVRepository(str(resolve_data_path(data_path))),
        reward_calculator=reward,
        topology_manager=TopologyManager(topology),
        episode_length=steps,
        enforce_msd_constraint=variant.enforce_msd_constraint,
    )
    env.traffic_scenario = scenario
    env.arrival_rate = 1.0  # Under stress
    env.ttl_range = (100, 500)
    return env


def load_policy_model(env: JOVDPREnv, model_path: Path):
    vec_env = DummyVecEnv([lambda: env])
    try:
        return MaskablePPO.load(str(model_path), env=vec_env, device="cpu")
    except Exception:
        return build_model_from_policy_weights(env, model_path)


def run_single_sweep_task(task: dict) -> dict:
    """Runs a single seed evaluation task for a parameter setting."""
    variant_key = task["variant_key"]
    variant = next(v for v in VARIANTS if v.key == variant_key)
    topology = task["topology"]
    scenario = task["scenario"]
    steps = task["steps"]
    seed = task["seed"]
    data_path = Path(task["data_path"])
    model_path = Path(task["model_path"])
    norm_path = Path(task["norm_path"])
    policy_source = task["policy_source"]
    param_type = task["param_type"]
    param_val = task["param_val"]

    np.random.seed(seed)
    random.seed(seed)

    env = make_env(variant, topology, data_path, steps, scenario)
    
    # Inject sweep parameters
    if param_type == "sla":
        env.inference_sla_threshold = float(param_val) if param_val is not None else None
        env.alert_cpu_threshold = 0.80
    elif param_type == "migration":
        env.inference_sla_threshold = None
        env.alert_cpu_threshold = float(param_val)

    model = load_policy_model(env, model_path)
    normalizer = load_normalizer(norm_path, model.get_env())

    obs, _ = env.reset(seed=seed)
    
    # Metric trackers
    accepted = 0
    sla_violations = 0
    admitted_msd_violations = 0
    evacuation_hits = 0
    switches = 0
    rewards = []
    latencies = []

    for _ in range(steps):
        obs_norm = normalized_obs(normalizer, obs)
        if variant.use_hard_mask:
            masks = np.array([env.action_masks()])
        else:
            masks = np.ones((1, env.action_space.n), dtype=bool)
        
        action, _ = model.predict(obs_norm, action_masks=masks, deterministic=True)
        action = action[0]

        obs, reward, done, _, info = env.step(action)
        
        if not info.get("skipped", False):
            accepted += int(bool(info.get("accepted", False)))
            admitted_msd_violations += int(bool(info.get("admitted_msd_violation", False)))
            latency = float(info.get("total_latency_ms", 0.0))
            threshold = env.inference_sla_threshold if env.inference_sla_threshold is not None else float(info.get("latency_threshold_ms", 80.0))
            sla_violations += int(latency > threshold)
            evacuation_hits += int(bool(info.get("evacuation_hit", False)))
            switches += int(bool(info.get("is_switching", False)))
            rewards.append(float(reward))
            latencies.append(latency)

        if done:
            obs, _ = env.reset(seed=seed)

    env.close()

    total_evaluated_steps = len(rewards) if rewards else 1
    safe_acceptance_rate = 100.0 * float(max(0, accepted - admitted_msd_violations)) / float(steps)
    sla_violation_rate = 100.0 * float(sla_violations) / float(steps)
    switching_rate = 100.0 * float(switches) / float(steps)
    avg_latency = float(np.mean(latencies)) if latencies else 0.0
    avg_reward = float(np.mean(rewards)) if rewards else 0.0

    return {
        "variant": variant.name,
        "variant_key": variant.key,
        "topology": topology,
        "scenario": scenario,
        "seed": seed,
        "param_type": param_type,
        "param_val": str(param_val) if param_val is not None else "None",
        "safe_acceptance_rate": safe_acceptance_rate,
        "sla_violation_rate": sla_violation_rate,
        "switching_rate": switching_rate,
        "avg_latency_ms": avg_latency,
        "avg_reward": avg_reward,
        "admitted_msd_violation_rate": 100.0 * float(admitted_msd_violations) / float(steps),
    }


def main():
    parser = argparse.ArgumentParser(description="HARP Parameter Sweep")
    parser.add_index = True
    parser.add_argument("--topology", type=str, required=True, help="vietnam, nsfnet, geant2")
    parser.add_argument("--scenario", type=str, default="heavy_tail", help="traffic scenario")
    parser.add_argument("--steps", type=int, default=3000, help="evaluation steps")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 100, 2024, 8888, 9999], help="seeds list")
    parser.add_argument("--data-path", type=str, default="data/real_telecom_combined.csv")
    parser.add_argument("--model-root", type=str, default="results/models")
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--workers", type=int, default=4, help="number of parallel workers")

    args = parser.parse_args()

    model_root = Path(args.model_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Define sweep parameter values
    # SLA thresholds (ms)
    sla_vals = [1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0, None]
    # alert thresholds
    mig_vals = [0.75, 0.80, 0.85, 0.90, 0.95]

    tasks = []

    # 2. Build tasks list
    for variant in VARIANTS:
        try:
            m_path, n_path, source = resolve_variant_model_paths(model_root, "v11", args.topology, variant)
        except FileNotFoundError as e:
            LOGGER.warning(f"Skipping variant {variant.name} on topology={args.topology}: {e}")
            continue

        for seed in args.seeds:
            # SLA sweeps
            for val in sla_vals:
                tasks.append({
                    "variant_key": variant.key,
                    "topology": args.topology,
                    "scenario": args.scenario,
                    "steps": args.steps,
                    "seed": seed,
                    "data_path": args.data_path,
                    "model_path": str(m_path),
                    "norm_path": str(n_path),
                    "policy_source": source,
                    "param_type": "sla",
                    "param_val": val,
                })
            # Migration sweeps
            for val in mig_vals:
                tasks.append({
                    "variant_key": variant.key,
                    "topology": args.topology,
                    "scenario": args.scenario,
                    "steps": args.steps,
                    "seed": seed,
                    "data_path": args.data_path,
                    "model_path": str(m_path),
                    "norm_path": str(n_path),
                    "policy_source": source,
                    "param_type": "migration",
                    "param_val": val,
                })

    LOGGER.info(f"Generated {len(tasks)} evaluation tasks. Running in parallel on {args.workers} workers...")

    results = []
    # Use ProcessPoolExecutor to run tasks in parallel
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_single_sweep_task, task): task for task in tasks}
        
        for future in as_completed(futures):
            try:
                res = future.result()
                results.append(res)
                # Print progress updates
                if len(results) % 20 == 0:
                    LOGGER.info(f"Progress: {len(results)}/{len(tasks)} completed.")
            except Exception as e:
                task_info = futures[future]
                LOGGER.error(f"Task failed (variant={task_info['variant_key']}, seed={task_info['seed']}): {e}")

    # 3. Export raw per-seed results
    raw_path = output_dir / f"{args.topology}_raw_ablation_parameter_sweep_5seeds.csv"
    import pandas as pd
    df_raw = pd.DataFrame(results)
    df_raw.to_csv(raw_path, index=False)
    LOGGER.info(f"Saved raw sweep results to {raw_path}")

    # 4. Aggregate across seeds (compute mean and std)
    group_cols = ["variant", "variant_key", "topology", "scenario", "param_type", "param_val"]
    numeric_cols = ["safe_acceptance_rate", "sla_violation_rate", "switching_rate", "avg_latency_ms", "avg_reward", "admitted_msd_violation_rate"]
    
    df_mean = df_raw.groupby(group_cols)[numeric_cols].mean().reset_index()
    df_std = df_raw.groupby(group_cols)[numeric_cols].std().reset_index()

    # Formatted output (mean ± std)
    df_final = df_mean.copy()
    for col in numeric_cols:
        df_final[f"{col}_mean"] = df_mean[col]
        df_final[f"{col}_std"] = df_std[col]

    final_path = output_dir / f"{args.topology}_master_ablation_parameter_sweep_5seeds.csv"
    df_final.to_csv(final_path, index=False)
    LOGGER.info(f"Saved master aggregated sweep results to {final_path}")
    
    print("FINISHED ALL PARAMETER SWEEP EVALUATIONS SUCCESSFULLY.")


if __name__ == "__main__":
    main()
