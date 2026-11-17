"""
HARP ablation study runner.

HARP: Hardware-Aware Reinforcement Policy.

The runner evaluates seven variants required for the revision ablation:
  1. HARP full
  2. HARP w/o GAT
  3. HARP w/o hard masking
  4. HARP w/o mask + unchecked admission
  5. HARP with soft MSD penalty
  6. HARP w/o adaptive penalty
  7. Soft MSD policy with the same runtime admission boundary enabled

This runner intentionally fails closed: every variant must have its own model
checkpoint and VecNormalize statistics. Silent fallback to the full HARP model
is forbidden because it can corrupt thesis data. Evaluation-only variants may
explicitly reuse a sibling checkpoint when their purpose is to isolate a runtime
guard rather than a separately trained policy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
from src.analytics.benchmark.revision.provenance import sha256_file  # noqa: E402
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
    attempted_cpu_violations: int = 0
    attempted_ram_violations: int = 0
    attempted_bw_violations: int = 0
    attempted_msd_violations: int = 0
    attempted_hard_violations: int = 0
    admitted_msd_violations: int = 0
    admitted_cpu_violations: int = 0
    admitted_ram_violations: int = 0
    admitted_bw_violations: int = 0
    admitted_hard_violations: int = 0
    sla_violations: int = 0
    evacuation_hits: int = 0
    switches: int = 0
    rewards: List[float] = field(default_factory=list)
    latencies: List[float] = field(default_factory=list)
    prop_latencies: List[float] = field(default_factory=list)
    srv6_latencies: List[float] = field(default_factory=list)
    queue_latencies: List[float] = field(default_factory=list)
    trace_records: List[dict] = field(default_factory=list)
    mask_candidate_counts: List[int] = field(default_factory=list)
    mask_total_candidates: List[int] = field(default_factory=list)
    mask_empty_steps: int = 0
    runtime_rejections: int = 0
    primary_cpu_rejections: int = 0
    primary_ram_rejections: int = 0
    primary_msd_rejections: int = 0
    primary_bw_rejections: int = 0
    primary_other_rejections: int = 0

    def collect(self, info: dict, reward: float) -> None:
        if "trace_request" in info:
            self.trace_records.append(dict(info["trace_request"]))
        if info.get("skipped", False):
            self.skipped += 1
            return

        self.steps += 1
        accepted = bool(info.get("accepted", False))
        if "mask_candidate_count" in info:
            self.mask_candidate_counts.append(int(info["mask_candidate_count"]))
            self.mask_total_candidates.append(int(info["mask_total_candidates"]))
            self.mask_empty_steps += int(bool(info.get("mask_empty", False)))
        self.runtime_rejections += int(not accepted)
        if not accepted:
            rejection_key = str(info.get("rejection_reason") or "other").lower()
            rejection_counter = {
                "cpu": "primary_cpu_rejections",
                "ram": "primary_ram_rejections",
                "msd": "primary_msd_rejections",
                "bw": "primary_bw_rejections",
            }.get(rejection_key, "primary_other_rejections")
            setattr(self, rejection_counter, getattr(self, rejection_counter) + 1)
        latency = float(info.get("total_latency_ms", 0.0))
        threshold = float(info.get("latency_threshold_ms", 0.0))

        self.accepted += int(accepted)
        attempted_cpu = bool(info.get("cpu_violation", False))
        attempted_ram = bool(info.get("ram_violation", False))
        attempted_bw = bool(info.get("bw_violation", False))
        attempted_msd = bool(info.get("msd_violation", False))
        self.attempted_cpu_violations += int(attempted_cpu)
        self.attempted_ram_violations += int(attempted_ram)
        self.attempted_bw_violations += int(attempted_bw)
        self.attempted_msd_violations += int(attempted_msd)
        self.attempted_hard_violations += int(
            attempted_cpu or attempted_ram or attempted_bw or attempted_msd
        )
        self.admitted_msd_violations += int(bool(info.get("admitted_msd_violation", False)))
        admitted_cpu = bool(info.get("admitted_cpu_violation", False))
        admitted_ram = bool(info.get("admitted_ram_violation", False))
        admitted_bw = bool(info.get("admitted_bw_violation", False))
        admitted_msd = bool(info.get("admitted_msd_violation", False))
        self.admitted_cpu_violations += int(admitted_cpu)
        self.admitted_ram_violations += int(admitted_ram)
        self.admitted_bw_violations += int(admitted_bw)
        self.admitted_hard_violations += int(admitted_cpu or admitted_ram or admitted_bw or admitted_msd)
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
        return pct(max(0, self.accepted - self.admitted_hard_violations), self.steps)

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

    @property
    def trace_sha256(self) -> str:
        serialized = json.dumps(self.trace_records, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

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
            "proposed_cpu_violation_rate": pct(self.attempted_cpu_violations, self.steps),
            "proposed_ram_violation_rate": pct(self.attempted_ram_violations, self.steps),
            "proposed_bw_violation_rate": pct(self.attempted_bw_violations, self.steps),
            "attempted_msd_violation_rate": self.attempted_msd_rate,
            "proposed_hard_violation_rate": pct(self.attempted_hard_violations, self.steps),
            "admitted_msd_violation_rate": self.admitted_msd_rate,
            "admitted_cpu_violation_rate": pct(self.admitted_cpu_violations, self.steps),
            "admitted_ram_violation_rate": pct(self.admitted_ram_violations, self.steps),
            "admitted_bw_violation_rate": pct(self.admitted_bw_violations, self.steps),
            "admitted_hard_violation_rate": pct(self.admitted_hard_violations, self.steps),
            "sla_violation_rate": self.sla_rate,
            "evacuation_hit_rate": self.evacuation_rate,
            "switching_rate": self.switching_rate,
            "avg_latency_ms": self.avg_latency,
            "avg_reward": self.avg_reward,
            "trace_sha256": self.trace_sha256,
            "trace_steps": len(self.trace_records),
            "mask_candidate_count_mean": mean(self.mask_candidate_counts),
            "mask_eliminated_candidate_rate": pct(
                sum(total - count for total, count in zip(self.mask_total_candidates, self.mask_candidate_counts)),
                sum(self.mask_total_candidates),
            ),
            "mask_empty_steps": self.mask_empty_steps,
            "runtime_rejections": self.runtime_rejections,
            "runtime_rejection_rate": pct(self.runtime_rejections, self.steps),
            "primary_cpu_rejection_rate": pct(self.primary_cpu_rejections, self.steps),
            "primary_ram_rejection_rate": pct(self.primary_ram_rejections, self.steps),
            "primary_msd_rejection_rate": pct(self.primary_msd_rejections, self.steps),
            "primary_bw_rejection_rate": pct(self.primary_bw_rejections, self.steps),
            "primary_other_rejection_rate": pct(self.primary_other_rejections, self.steps),
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
        use_gat_model=False,
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
        key="harp_soft_msd_admission",
        model_key="harp_soft_msd_penalty",
        name="Soft MSD + runtime admission",
        hypothesis="Evaluate the soft-MSD-trained, unmasked policy with the independent MSD admission check restored.",
        use_hard_mask=False,
        enforce_msd_constraint=True,
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
        f"--variant {checkpoint_key} --topology {topology}"
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


def load_policy_model(env: JOVDPREnv, model_path: Path, variant: Variant):
    vec_env = DummyVecEnv([lambda: env])
    custom_objects = None
    if not variant.use_gat_model:
        from src.analytics.training.train_harp_ablation import FlatMLPExtractor
        custom_objects = {"policy_kwargs": {
            "features_extractor_class": FlatMLPExtractor,
            "features_extractor_kwargs": {"features_dim": 256},
            "net_arch": {"pi": [256, 128], "vf": [256, 128]},
        }}
    # Do not catch arbitrary load errors or rebuild a different architecture.
    model = MaskablePPO.load(
        str(model_path), env=vec_env, device="cpu", custom_objects=custom_objects
    )
    if model.observation_space != env.observation_space:
        raise ValueError(
            f"Observation-space mismatch for {model_path}: "
            f"checkpoint={model.observation_space}, env={env.observation_space}"
        )
    if model.action_space != env.action_space:
        raise ValueError(
            f"Action-space mismatch for {model_path}: "
            f"checkpoint={model.action_space}, env={env.action_space}"
        )
    return model


def preflight_variant(
    variant: Variant, topology: str, scenario: str, steps: int,
    data_path: Path, model_path: Path, norm_path: Path,
    arrival_rate: float, ttl_range: tuple[int, int],
) -> None:
    """Load the exact checkpoint/normalizer and verify spaces before runs."""
    if not model_path.is_file() or not norm_path.is_file():
        raise FileNotFoundError(f"Missing artifacts for {variant.key}: {model_path}; {norm_path}")
    env = make_env(variant, topology, data_path, steps, scenario, arrival_rate, ttl_range)
    try:
        model = load_policy_model(env, model_path, variant)
        normalizer = load_normalizer(norm_path, model.get_env())
        obs, _ = env.reset(seed=0)
        normalized = normalized_obs(normalizer, obs)
        if normalized.shape != (1, env.observation_space.shape[0]):
            raise ValueError(
                f"Normalizer dimension mismatch for {variant.key}: {normalized.shape}"
            )
        if variant.use_hard_mask:
            mask = env.action_masks()
            if mask.shape != (env.action_space.n,):
                raise ValueError(f"Invalid action-mask shape for {variant.key}: {mask.shape}")
    finally:
        env.close()


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
    model = load_policy_model(env, model_path, variant)
    normalizer = load_normalizer(norm_path, model.get_env())

    obs, _ = env.reset(seed=seed)
    for _ in range(steps):
        obs_norm = normalized_obs(normalizer, obs)
        if variant.use_hard_mask:
            mask = env.action_masks()
        else:
            mask = np.ones(env.action_space.n, dtype=bool)
        mask_count = int(mask.sum())
        prediction_mask = mask if mask_count else np.ones(env.action_space.n, dtype=bool)
        masks = np.array([prediction_mask])
        action, _ = model.predict(obs_norm, action_masks=masks, deterministic=True)
        action = action[0]

        obs, reward, done, _, info = env.step(action)
        info.update({
            "mask_candidate_count": mask_count,
            "mask_total_candidates": int(env.action_space.n),
            "mask_empty": mask_count == 0,
        })
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


def validate_coverage(results: List[AblationMetrics], variants: List[Variant], seeds: List[int], steps: int) -> None:
    expected = {(variant.key, seed) for variant in variants for seed in seeds}
    observed = [(result.key, result.seed) for result in results]
    if len(observed) != len(set(observed)):
        raise RuntimeError("Ablation output contains duplicate variant/seed rows")
    missing = expected - set(observed)
    extra = set(observed) - expected
    if missing or extra:
        raise RuntimeError(f"Ablation coverage mismatch: missing={sorted(missing)}, extra={sorted(extra)}")
    incomplete = [
        (result.key, result.seed, result.steps + result.skipped)
        for result in results if result.steps + result.skipped != steps
    ]
    if incomplete:
        raise RuntimeError(f"Ablation runs have incomplete step coverage (expected {steps}): {incomplete}")
    incomplete_traces = [
        (result.key, result.seed, len(result.trace_records))
        for result in results if len(result.trace_records) != steps
    ]
    if incomplete_traces:
        raise RuntimeError(f"Ablation workload trace coverage mismatch (expected {steps}): {incomplete_traces}")
    for seed in seeds:
        seed_results = [result for result in results if result.seed == seed]
        hashes = {result.trace_sha256 for result in seed_results}
        if len(hashes) != 1:
            raise RuntimeError(
                f"Ablation variants received different workload traces for seed={seed}: {sorted(hashes)}"
            )
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HARP ablation studies.")
    parser.add_argument("--topology", default="vietnam", choices=["vietnam", "nsfnet", "geant2"])
    parser.add_argument("--scenario", default="heavy_tail", choices=["uniform", "bursty", "heavy_tail", "chaos"])
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+", help="Evaluation seeds; overrides --seed.")
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

    seeds = args.seeds or [args.seed]
    # Resolve and validate every model/normalizer before starting any run.
    artifact_map = {}
    for variant in VARIANTS:
        artifact_map[variant.key] = resolve_variant_model_paths(
            model_root=Path(args.model_root), version=args.version,
            topology=args.topology, variant=variant,
        )
    for variant in VARIANTS:
        model_file, norm_file, _ = artifact_map[variant.key]
        preflight_variant(
            variant, args.topology, args.scenario, min(args.steps, 2),
            data_path, model_file, norm_file, args.arrival_rate, ttl_range,
        )

    results = []
    for seed in seeds:
        for variant in VARIANTS:
            variant_model_path, variant_norm_path, policy_source = artifact_map[variant.key]
            LOGGER.info("seed=%s %s uses %s", seed, variant.name, policy_source)
            results.append(run_variant(
                variant=variant, topology=args.topology, scenario=args.scenario,
                steps=args.steps, seed=seed, data_path=data_path,
                model_path=variant_model_path, norm_path=variant_norm_path,
                policy_source=policy_source, arrival_rate=args.arrival_rate,
                ttl_range=ttl_range,
            ))

    validate_coverage(results, VARIANTS, seeds, args.steps)
    print_summary(results)
    output_path = Path(args.output_dir) / args.topology / args.scenario
    write_outputs(output_path, results, VARIANTS, model_path, norm_path)
    resolved_data = resolve_data_path(data_path)
    manifest = {
        "protocol": "ablation-v3", "topology": args.topology,
        "scenario": args.scenario, "seeds": seeds, "steps": args.steps,
        "arrival_rate": args.arrival_rate, "ttl_range": list(ttl_range),
        "data_path": str(resolved_data), "data_sha256": sha256_file(resolved_data),
        "variants": [asdict(variant) for variant in VARIANTS],
        "accounting": {
            "request_denominator": "offered, non-skipped requests",
            "proposed_violation_rates": "selected proposal; CPU/RAM/BW/MSD rates may overlap",
            "proposed_hard_violation_rate": "union of selected-proposal CPU/RAM/BW/MSD violations",
            "admitted_hard_violation_rate": "union of admitted CPU/RAM/BW/MSD violations",
            "safe_acceptance_rate": "accepted requests minus unique admitted hard-violating requests, divided by offered requests",
            "primary_rejection_rates": "one non-overlapping rejection cause per rejected offered request",
            "matched_trace_requirement": "one trace SHA-256 per evaluation seed across all variants",
        },
        "source_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(Path(__file__).with_name("training") / "train_harp_ablation.py"): sha256_file(
                Path(__file__).with_name("training") / "train_harp_ablation.py"),
            str(Path(__file__).parents[1] / "orchestration/jo_vdpr/env.py"): sha256_file(
                Path(__file__).parents[1] / "orchestration/jo_vdpr/env.py"),
            str(Path(__file__).parents[1] / "orchestration/jo_vdpr/rewards.py"): sha256_file(
                Path(__file__).parents[1] / "orchestration/jo_vdpr/rewards.py"),
            str(Path(__file__).parents[1] / "orchestration/jo_vdpr/topology.py"): sha256_file(
                Path(__file__).parents[1] / "orchestration/jo_vdpr/topology.py"),
        },
        "artifacts": {
            key: {"model_path": str(paths[0]), "model_sha256": sha256_file(paths[0]),
                  "normalizer_path": str(paths[1]), "normalizer_sha256": sha256_file(paths[1]),
                  "policy_source": paths[2]}
            for key, paths in artifact_map.items()
        },
        "chaos_profile": {
            "calm_to_stress": 0.08, "stress_to_calm": 0.35,
            "cpu_multiplier": 2.5, "ram_multiplier": 1.75, "sid_increment": 2,
        },
    }
    (output_path / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
