"""
HARP ablation study runner.

HARP: Hardware-Aware Reinforcement Policy.

The runner evaluates six variants required by the thesis defense:
  1. HARP full
  2. HARP w/o GAT
  3. HARP w/o hard masking
  4. HARP w/o mask + unchecked admission
  5. HARP with soft MSD penalty
  6. HARP w/o adaptive penalty

This runner intentionally fails closed: every variant must have its own model
checkpoint and VecNormalize statistics. Silent fallback to the full HARP model
is forbidden because it can corrupt thesis data. Evaluation-only variants may
explicitly reuse a sibling checkpoint when their purpose is to isolate a runtime
guard rather than a separately trained policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from src.analytics.benchmark.benchmark_algorithm.model_loader import (  # noqa: E402
    build_model_from_policy_weights,
    load_normalizer,
    normalized_obs,
)
from src.infrastructure.persistence.csv_repository import CSVRepository  # noqa: E402
from src.orchestration.jo_vdpr.env import JOVDPREnv  # noqa: E402
from src.orchestration.jo_vdpr.rewards import RewardCalculator  # noqa: E402
from src.orchestration.jo_vdpr.topology import TopologyManager  # noqa: E402


LOGGER = logging.getLogger("harp-ablation")


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


@dataclass
class AblationMetrics:
    key: str
    name: str
    hypothesis: str
    topology: str
    scenario: str
    seed: int
    policy_source: str
    steps: int = 0
    accepted: int = 0
    skipped: int = 0
    attempted_msd_violations: int = 0
    admitted_msd_violations: int = 0
    sla_violations: int = 0
    evacuation_hits: int = 0
    switches: int = 0
    rewards: List[float] = field(default_factory=list)
    latencies: List[float] = field(default_factory=list)
    prop_latencies: List[float] = field(default_factory=list)
    srv6_latencies: List[float] = field(default_factory=list)
    queue_latencies: List[float] = field(default_factory=list)

    def collect(self, info: dict, reward: float) -> None:
        if info.get("skipped", False):
            self.skipped += 1
            return

        self.steps += 1
        accepted = bool(info.get("accepted", False))
        latency = float(info.get("total_latency_ms", 0.0))
        threshold = float(info.get("latency_threshold_ms", 0.0))

        self.accepted += int(accepted)
        self.attempted_msd_violations += int(bool(info.get("msd_violation", False)))
        self.admitted_msd_violations += int(bool(info.get("admitted_msd_violation", False)))
        self.sla_violations += int(threshold > 0.0 and latency > threshold)
        self.evacuation_hits += int(bool(info.get("evacuation_hit", False)))
        self.switches += int(bool(info.get("is_switching", False)))
        self.rewards.append(float(reward))
        self.latencies.append(latency)
        self.prop_latencies.append(float(info.get("prop_latency_ms", 0.0)))
        self.srv6_latencies.append(float(info.get("srv6_latency_ms", 0.0)))
        self.queue_latencies.append(float(info.get("queue_latency_ms", 0.0)))

    @property
    def acceptance_rate(self) -> float:
        return pct(self.accepted, self.steps)

    @property
    def attempted_msd_rate(self) -> float:
        return pct(self.attempted_msd_violations, self.steps)

    @property
    def admitted_msd_rate(self) -> float:
        return pct(self.admitted_msd_violations, self.steps)

    @property
    def safe_acceptance_rate(self) -> float:
        return pct(max(0, self.accepted - self.admitted_msd_violations), self.steps)

    @property
    def sla_rate(self) -> float:
        return pct(self.sla_violations, self.steps)

    @property
    def evacuation_rate(self) -> float:
        return pct(self.evacuation_hits, self.steps)

    @property
    def switching_rate(self) -> float:
        return pct(self.switches, self.steps)

    @property
    def avg_reward(self) -> float:
        return mean(self.rewards)

    @property
    def avg_latency(self) -> float:
        return mean(self.latencies)

    def row(self) -> Dict[str, object]:
        return {
            "variant": self.name,
            "key": self.key,
            "hypothesis": self.hypothesis,
            "topology": self.topology,
            "scenario": self.scenario,
            "seed": self.seed,
            "policy_source": self.policy_source,
            "steps": self.steps,
            "acceptance_rate": self.acceptance_rate,
            "safe_acceptance_rate": self.safe_acceptance_rate,
            "attempted_msd_violation_rate": self.attempted_msd_rate,
            "admitted_msd_violation_rate": self.admitted_msd_rate,
            "sla_violation_rate": self.sla_rate,
            "evacuation_hit_rate": self.evacuation_rate,
            "switching_rate": self.switching_rate,
            "avg_latency_ms": self.avg_latency,
            "avg_reward": self.avg_reward,
        }


VARIANTS: List[Variant] = [
    Variant(
        key="harp_full",
        name="HARP full",
        hypothesis="Full hardware-aware GAT policy with hard safety and adaptive SLA/migration penalties.",
    ),
    Variant(
        key="harp_wo_gat",
        name="HARP w/o GAT",
        hypothesis="Topology encoder contribution: replace GAT with a parameter-matched flat MLP policy.",
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


def pct(numerator: int, denominator: int) -> float:
    return 100.0 * float(numerator) / float(denominator) if denominator else 0.0


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return float(np.mean(vals)) if vals else 0.0


def resolve_data_path(path: Path) -> Path:
    if path.exists():
        return path
    fallback = Path("data/real_telecom_combined.csv")
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Cannot find data file: {path}")


def resolve_model_paths(model_root: Path, version: str, topology: str) -> tuple[Path, Path]:
    candidates = [
        model_root / version / f"dgrl_{version}_final_{topology}.zip",
        model_root / version / f"dgrl_{version}_{topology}.zip",
        model_root / f"dgrl_{version}_final_{topology}.zip",
        model_root / f"dgrl_{version}_{topology}.zip",
    ]
    norm_candidates = [
        model_root / version / f"vec_normalize_{version}_{topology}.pkl",
        model_root / f"vec_normalize_{version}_{topology}.pkl",
    ]

    model_path = next((path for path in candidates if path.exists()), candidates[0])
    norm_path = next((path for path in norm_candidates if path.exists()), norm_candidates[0])
    return model_path, norm_path


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
            if checkpoint_key != variant.key:
                source += f" (reused for {variant.key})"
            return model, norm, source

    searched = "\n".join(str(root) for root in variant_roots)
    raise FileNotFoundError(
        f"Missing strict ablation checkpoint for {variant.key} on topology={topology}.\n"
        f"Checkpoint key searched: {checkpoint_key}\n"
        f"Expected one model and one variant VecNormalize file under:\n{searched}\n"
        f"Train it first with: python -m src.analytics.training.train_harp_ablation "
        f"--variant {variant.key} --topology {topology}"
    )


def make_env(
    variant: Variant,
    topology: str,
    data_path: Path,
    steps: int,
    scenario: str,
    arrival_rate: float,
    ttl_range: tuple[int, int],
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
    env.arrival_rate = arrival_rate
    env.ttl_range = ttl_range
    return env


def load_policy_model(env: JOVDPREnv, model_path: Path):
    vec_env = DummyVecEnv([lambda: env])
    try:
        return MaskablePPO.load(str(model_path), env=vec_env, device="cpu")
    except Exception:
        return build_model_from_policy_weights(env, model_path)


def run_variant(
    variant: Variant,
    topology: str,
    scenario: str,
    steps: int,
    seed: int,
    data_path: Path,
    model_path: Path,
    norm_path: Path,
    policy_source: str,
    arrival_rate: float,
    ttl_range: tuple[int, int],
) -> AblationMetrics:
    np.random.seed(seed)
    random.seed(seed)

    env = make_env(variant, topology, data_path, steps, scenario, arrival_rate, ttl_range)
    metrics = AblationMetrics(
        key=variant.key,
        name=variant.name,
        hypothesis=variant.hypothesis,
        topology=topology,
        scenario=scenario,
        seed=seed,
        policy_source=policy_source,
    )

    if not model_path.exists() or not norm_path.exists():
        raise FileNotFoundError(f"Missing HARP ablation checkpoint or normalizer: {model_path}, {norm_path}")
    model = load_policy_model(env, model_path)
    normalizer = load_normalizer(norm_path, model.get_env())

    obs, _ = env.reset(seed=seed)
    for _ in range(steps):
        obs_norm = normalized_obs(normalizer, obs)
        if variant.use_hard_mask:
            masks = np.array([env.action_masks()])
        else:
            masks = np.ones((1, env.action_space.n), dtype=bool)
        action, _ = model.predict(obs_norm, action_masks=masks, deterministic=True)
        action = action[0]

        obs, reward, done, _, info = env.step(action)
        metrics.collect(info, reward)
        if done:
            obs, _ = env.reset(seed=seed)

    env.close()
    return metrics


def write_outputs(
    output_dir: Path,
    results: List[AblationMetrics],
    variants: List[Variant],
    model_path: Path,
    norm_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [result.row() for result in results]

    csv_path = output_dir / "harp_ablation_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    json_path = output_dir / "harp_ablation_results.json"
    payload = {
        "method": "HARP",
        "method_full_name": "Hardware-Aware Reinforcement Policy",
        "default_model_path": str(model_path),
        "default_normalizer_path": str(norm_path),
        "variants": [asdict(variant) for variant in variants],
        "results": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    plot_dashboard(output_dir, results)
    LOGGER.info("Saved %s and %s", csv_path, json_path)


def plot_dashboard(output_dir: Path, results: List[AblationMetrics]) -> None:
    label_map = {
        "HARP full": "Full",
        "HARP w/o GAT": "w/o GAT",
        "HARP w/o hard masking": "NoMask",
        "HARP w/o mask + unchecked admission": "NoMask\nUnchecked",
        "HARP with soft MSD penalty": "SoftMSD",
        "HARP w/o adaptive penalty": "NoAdapt",
    }
    labels = [label_map.get(metric.name, metric.name.replace("HARP ", "")) for metric in results]
    colors = ["#0f766e", "#2563eb", "#d97706", "#ea580c", "#dc2626", "#7c3aed"]
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("HARP Ablation Study: Hardware-Aware Reinforcement Policy", fontsize=15, fontweight="bold")

    def bar(ax, values, title, ylabel, ymax: Optional[float] = None) -> None:
        bars = ax.bar(labels, values, color=colors[: len(values)], edgecolor="#111827", linewidth=0.8)
        ax.set_title(title, fontweight="bold")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=18)
        ax.grid(axis="y", linestyle="--", alpha=0.28)
        if ymax is not None:
            ax.set_ylim(0, ymax)
        offset = (ymax or max(values + [1.0])) * 0.015
        for rect, value in zip(bars, values):
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                rect.get_height() + offset,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

    bar(axes[0, 0], [m.safe_acceptance_rate for m in results], "Safe Acceptance Rate ↑", "%", ymax=105)
    bar(axes[0, 1], [m.attempted_msd_rate for m in results], "Attempted MSD Violations ↓", "%")
    bar(axes[0, 2], [m.admitted_msd_rate for m in results], "Admitted MSD Violations ↓", "%")
    bar(axes[1, 0], [m.sla_rate for m in results], "SLA Violations ↓", "%")
    bar(axes[1, 1], [m.avg_latency for m in results], "Average Latency ↓", "ms")

    ax = axes[1, 2]
    x = np.arange(len(results))
    prop = [mean(m.prop_latencies) for m in results]
    srv6 = [mean(m.srv6_latencies) for m in results]
    queue = [mean(m.queue_latencies) for m in results]
    ax.bar(x, prop, label="Propagation", color="#0891b2")
    ax.bar(x, srv6, bottom=prop, label="SRv6", color="#f59e0b")
    ax.bar(x, queue, bottom=[p + s for p, s in zip(prop, srv6)], label="Queue", color="#ef4444")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18)
    ax.set_title("Latency Breakdown", fontweight="bold")
    ax.set_ylabel("ms")
    ax.grid(axis="y", linestyle="--", alpha=0.28)
    ax.legend()

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(output_dir / "harp_ablation_dashboard.png", dpi=220, bbox_inches="tight")
    fig.savefig(output_dir / "harp_ablation_dashboard.pdf", dpi=220, bbox_inches="tight")
    plt.close(fig)


def print_summary(results: List[AblationMetrics]) -> None:
    header = (
        f"{'Variant':<36} | {'Accept':>7} | {'Safe':>7} | {'MSD try':>7} | {'MSD admit':>9} | "
        f"{'SLA':>7} | {'Latency':>8} | {'Reward':>8}"
    )
    print("\n" + "=" * len(header))
    print(header)
    print("=" * len(header))
    for metric in results:
        print(
            f"{metric.name:<36} | {metric.acceptance_rate:>6.1f}% | "
            f"{metric.safe_acceptance_rate:>6.1f}% | "
            f"{metric.attempted_msd_rate:>6.1f}% | {metric.admitted_msd_rate:>8.1f}% | "
            f"{metric.sla_rate:>6.1f}% | {metric.avg_latency:>7.2f} | {metric.avg_reward:>8.1f}"
        )
    print("=" * len(header))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HARP ablation studies.")
    parser.add_argument("--topology", default="vietnam", choices=["vietnam", "nsfnet", "geant2"])
    parser.add_argument("--scenario", default="heavy_tail", choices=["uniform", "bursty", "heavy_tail"])
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--arrival-rate", type=float, default=1.0)
    parser.add_argument("--ttl-min", type=int, default=100)
    parser.add_argument("--ttl-max", type=int, default=500)
    parser.add_argument("--version", default="v11")
    parser.add_argument("--data-path", default="data/processed/real_telecom_combined.csv")
    parser.add_argument("--model-root", default="results/models")
    parser.add_argument("--output-dir", default="results/figures/ablation")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()
    data_path = Path(args.data_path)
    model_path, norm_path = resolve_model_paths(Path(args.model_root), args.version, args.topology)
    ttl_range = (args.ttl_min, args.ttl_max)

    LOGGER.info("Running HARP ablation on topology=%s scenario=%s steps=%s", args.topology, args.scenario, args.steps)
    LOGGER.info("Default full model path is recorded only for metadata: %s", model_path)

    results = []
    for variant in VARIANTS:
        variant_model_path, variant_norm_path, policy_source = resolve_variant_model_paths(
            model_root=Path(args.model_root),
            version=args.version,
            topology=args.topology,
            variant=variant,
        )
        LOGGER.info("%s uses %s", variant.name, policy_source)
        results.append(
            run_variant(
                variant=variant,
                topology=args.topology,
                scenario=args.scenario,
                steps=args.steps,
                seed=args.seed,
                data_path=data_path,
                model_path=variant_model_path,
                norm_path=variant_norm_path,
                policy_source=policy_source,
                arrival_rate=args.arrival_rate,
                ttl_range=ttl_range,
            )
        )

    print_summary(results)
    write_outputs(Path(args.output_dir), results, VARIANTS, model_path, norm_path)


if __name__ == "__main__":
    main()
