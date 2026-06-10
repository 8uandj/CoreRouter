"""
Train HARP ablation checkpoints.

This script creates variant-specific checkpoints for the five thesis ablation
settings. Evaluation then uses `src.analytics.ablation_study`, which prefers
checkpoints under:

    results/models/ablation/<variant_key>/

The important distinction is that `w/o GAT` and `w/o adaptive penalty` become
training ablations, not just reward-time/evaluation toggles.
"""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List

import numpy as np
import torch.nn as nn
from gymnasium import spaces
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor, VecNormalize

from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import TopologyManager


LOGGER = logging.getLogger("harp-ablation-train")


@dataclass(frozen=True)
class TrainVariant:
    key: str
    use_gat: bool = True
    use_mask: bool = True
    enforce_msd_constraint: bool = True
    soft_msd_penalty: bool = False
    adaptive_penalty: bool = True


VARIANTS: Dict[str, TrainVariant] = {
    "harp_full": TrainVariant("harp_full"),
    "harp_wo_gat": TrainVariant("harp_wo_gat", use_gat=False),
    "harp_wo_hard_masking": TrainVariant("harp_wo_hard_masking", use_mask=False),
    "harp_soft_msd_penalty": TrainVariant(
        "harp_soft_msd_penalty",
        use_mask=False,
        enforce_msd_constraint=False,
        soft_msd_penalty=True,
    ),
    "harp_wo_adaptive_penalty": TrainVariant("harp_wo_adaptive_penalty", adaptive_penalty=False),
}


class NoMaskJOVDPREnv(JOVDPREnv):
    def action_masks(self) -> np.ndarray:
        return np.ones(2 * self.num_nodes, dtype=bool)


class FlatMLPExtractor(BaseFeaturesExtractor):
    """Parameter-matched topology-blind extractor.

    For the 10-node Vietnam observation (N*6+13 = 73 dims), this extractor has
    roughly the same order of trainable parameters as the GAT extractor. The
    point is to remove graph structure, not to shrink model capacity.
    """

    def __init__(self, observation_space: spaces.Box, features_dim: int = 256):
        super().__init__(observation_space, features_dim=features_dim)
        obs_dim = observation_space.shape[0]
        self.net = nn.Sequential(
            nn.Linear(obs_dim, 768),
            nn.LayerNorm(768),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(768, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(512, features_dim),
            nn.ReLU(),
        )

    def forward(self, obs):
        return self.net(obs)


class EntropyDecayCallback(BaseCallback):
    def __init__(self, initial: float, final: float, total_steps: int):
        super().__init__()
        self.initial = initial
        self.final = final
        self.total_steps = max(1, total_steps)

    def _on_step(self) -> bool:
        progress = min(1.0, self.num_timesteps / self.total_steps)
        new_ent = self.final + 0.5 * (self.initial - self.final) * (1 + np.cos(np.pi * progress))
        self.model.ent_coef = float(new_ent)
        return True


class AdaptivePenaltyCallback(BaseCallback):
    def __init__(
        self,
        target_rate: float = 0.015,
        update_freq: int = 5120,
        lr_lambda: float = 10.0,
        lambda_min: float = -3000.0,
        lambda_max: float = -5.0,
    ):
        super().__init__()
        self.target_rate = target_rate
        self.update_freq = update_freq
        self.lr_lambda = lr_lambda
        self.lambda_min = lambda_min
        self.lambda_max = lambda_max
        self.current_lambda = -100.0
        self._viol_buffer: List[float] = []

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            if "latency_violation_rate" in info:
                self._viol_buffer.append(float(info["latency_violation_rate"]))

        if self.n_calls % self.update_freq == 0 and self._viol_buffer:
            avg_viol = float(np.mean(self._viol_buffer))
            self._viol_buffer.clear()
            delta = self.lr_lambda * (avg_viol - self.target_rate)
            self.current_lambda = float(np.clip(self.current_lambda - delta, self.lambda_min, self.lambda_max))
            if hasattr(self.training_env, "env_method"):
                self.training_env.env_method("update_reward_lambda", self.current_lambda)
            LOGGER.info("step=%s sla_viol=%.2f%% lambda=%.1f", self.num_timesteps, avg_viol * 100, self.current_lambda)
        return True


def resolve_data_path(path: Path) -> Path:
    if path.exists():
        return path
    fallback = Path("data/real_telecom_combined.csv")
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Cannot find data file: {path}")


def make_env_fn(
    rank: int,
    seed: int,
    data_path: Path,
    topology_name: str,
    variant: TrainVariant,
    episode_length: int,
    scenario: str,
) -> Callable[[], JOVDPREnv]:
    def _init() -> JOVDPREnv:
        reward = RewardCalculator(
            lambda_latency=-100.0 if variant.adaptive_penalty else 0.0,
            switching_cost=-10.0 if variant.adaptive_penalty else 0.0,
            evacuation_penalty=-50.0 if variant.adaptive_penalty else 0.0,
            msd_violation_penalty=-100.0 if variant.soft_msd_penalty else 0.0,
        )
        env_cls = JOVDPREnv if variant.use_mask else NoMaskJOVDPREnv
        env = env_cls(
            repository=CSVRepository(str(resolve_data_path(data_path))),
            reward_calculator=reward,
            topology_manager=TopologyManager(topology_name),
            episode_length=episode_length,
            enforce_msd_constraint=variant.enforce_msd_constraint,
        )
        env.traffic_scenario = scenario
        env.arrival_rate = 1.0
        env.ttl_range = (100, 500)
        env.reset(seed=seed + rank)
        return env

    set_random_seed(seed)
    return _init


def linear_schedule(initial_value: float):
    def schedule(progress_remaining: float) -> float:
        return progress_remaining * initial_value

    return schedule


def build_model(variant: TrainVariant, env, topology_name: str, learning_rate: float, seed: int):
    if variant.use_gat:
        topo = TopologyManager(topology_name)
        policy = GNNActorCriticPolicy
        policy_kwargs = dict(
            num_nodes=topo.num_nodes,
            adj_matrix=topo.adj_matrix,
            gat_hidden=64,
            gat_heads=4,
            features_dim=256,
            net_arch=dict(pi=[256, 128], vf=[256, 128]),
        )
    else:
        policy = "MlpPolicy"
        policy_kwargs = dict(
            features_extractor_class=FlatMLPExtractor,
            features_extractor_kwargs=dict(features_dim=256),
            net_arch=dict(pi=[256, 128], vf=[256, 128]),
        )

    model = MaskablePPO(
        policy=policy,
        env=env,
        learning_rate=linear_schedule(learning_rate),
        n_steps=512,
        batch_size=256,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.05,
        vf_coef=0.7,
        max_grad_norm=0.5,
        policy_kwargs=policy_kwargs,
        verbose=1,
        seed=seed,
        device="auto",
    )
    trainable_params = sum(p.numel() for p in model.policy.parameters() if p.requires_grad)
    LOGGER.info("%s policy trainable parameters: %s", variant.key, f"{trainable_params:,}")
    return model


def train_variant(args: argparse.Namespace, variant: TrainVariant) -> None:
    out_dir = Path(args.output_root) / variant.key
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = resolve_data_path(Path(args.data_path))

    env_fns = [
        make_env_fn(i, args.seed, data_path, args.topology, variant, args.episode_length, args.scenario)
        for i in range(args.n_envs)
    ]
    if args.n_envs > 1:
        train_env = SubprocVecEnv(env_fns)
    else:
        train_env = DummyVecEnv(env_fns)
    train_env = VecMonitor(train_env)
    train_env = VecNormalize(train_env, norm_obs=True, norm_reward=True, clip_obs=10.0, gamma=0.99)

    model = build_model(variant, train_env, args.topology, args.learning_rate, args.seed)

    callbacks = [
        EntropyDecayCallback(initial=0.05, final=0.00005, total_steps=args.total_steps),
        CheckpointCallback(
            save_freq=max(args.checkpoint_freq // max(1, args.n_envs), 1),
            save_path=str(out_dir),
            name_prefix=f"dgrl_v11_ckpt_{variant.key}_{args.topology}",
        ),
    ]
    if variant.adaptive_penalty:
        callbacks.append(AdaptivePenaltyCallback(update_freq=512 * max(1, args.n_envs)))

    LOGGER.info("Training %s for %s steps on %s", variant.key, args.total_steps, args.topology)
    model.learn(total_timesteps=args.total_steps, callback=CallbackList(callbacks), tb_log_name=variant.key)

    model_path = out_dir / f"dgrl_v11_{variant.key}_{args.topology}.zip"
    norm_path = out_dir / f"vec_normalize_v11_{variant.key}_{args.topology}.pkl"
    model.save(str(model_path))
    train_env.save(str(norm_path))
    train_env.close()

    LOGGER.info("Saved %s", model_path)
    LOGGER.info("Saved %s", norm_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train HARP ablation checkpoints.")
    parser.add_argument("--variant", default="all", choices=["all"] + sorted(VARIANTS.keys()))
    parser.add_argument("--topology", default="vietnam", choices=["vietnam", "nsfnet", "geant2"])
    parser.add_argument("--scenario", default="heavy_tail", choices=["uniform", "bursty", "heavy_tail"])
    parser.add_argument("--total-steps", type=int, default=500_000)
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--episode-length", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--checkpoint-freq", type=int, default=250_000)
    parser.add_argument("--data-path", default="data/real_telecom_combined.csv")
    parser.add_argument("--output-root", default="results/models/ablation")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()
    selected = list(VARIANTS.values()) if args.variant == "all" else [VARIANTS[args.variant]]
    for variant in selected:
        train_variant(args, variant)


if __name__ == "__main__":
    main()
