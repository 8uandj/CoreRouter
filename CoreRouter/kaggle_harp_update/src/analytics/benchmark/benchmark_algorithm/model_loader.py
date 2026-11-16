from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Tuple

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv

from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy


class NpzNormalizer:
    def __init__(self, path: Path) -> None:
        stats = np.load(path)
        self.obs_mean = stats["obs_mean"].astype(np.float32)
        self.obs_var = stats["obs_var"].astype(np.float32)
        self.clip_obs = float(stats["clip_obs"])
        self.epsilon = float(stats["epsilon"])
        self.norm_obs = bool(stats["norm_obs"])

    def normalize_obs(self, obs: np.ndarray) -> np.ndarray:
        if not self.norm_obs:
            return obs
        normalized = (obs - self.obs_mean) / np.sqrt(self.obs_var + self.epsilon)
        return np.clip(normalized, -self.clip_obs, self.clip_obs).astype(np.float32)


def load_normalizer(norm_path: Path, venv=None):
    try:
        from stable_baselines3.common.vec_env import VecNormalize
        normalizer = VecNormalize.load(str(norm_path), venv)
        normalizer.training = False
        normalizer.norm_reward = False
        return normalizer
    except Exception:
        npz_path = norm_path.with_suffix(".npz")
        if npz_path.exists():
            return NpzNormalizer(npz_path)
        raise


def normalized_obs(normalizer, obs: np.ndarray) -> np.ndarray:
    obs_2d = obs.reshape(1, -1).astype(np.float32)
    if hasattr(normalizer, "normalize_obs"):
        return normalizer.normalize_obs(obs_2d)
    return obs_2d


def build_model_from_policy_weights(raw_env, model_path: Path) -> MaskablePPO:
    vec_env = DummyVecEnv([lambda: raw_env])
    policy_kwargs = dict(
        num_nodes=raw_env.topo.num_nodes,
        adj_matrix=raw_env.topo.adj_matrix,
        gat_hidden=64,
        gat_heads=4,
        features_dim=256,
        net_arch=dict(pi=[256, 128], vf=[256, 128]),
    )
    model = MaskablePPO(
        GNNActorCriticPolicy,
        vec_env,
        policy_kwargs=policy_kwargs,
        device="cpu",
    )
    zip_path = _flatten_single_root_archive(model_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        with archive.open("policy.pth") as handle:
            model.policy.load_state_dict(
                torch.load(io.BytesIO(handle.read()), map_location="cpu", weights_only=False)
            )
    return model


def _flatten_single_root_archive(path: Path) -> Path:
    with zipfile.ZipFile(path, "r") as source:
        names = [name for name in source.namelist() if not name.endswith("/")]
        if "policy.pth" in names:
            return path
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            return path
        root = next(iter(roots))
        if f"{root}/policy.pth" not in names:
            return path
        target = Path("/tmp") / f"{path.stem}-flat-{path.stat().st_size}.zip"
        if target.exists():
            return target
        with zipfile.ZipFile(target, "w") as out:
            prefix = f"{root}/"
            for name in names:
                if name.startswith(prefix):
                    out.writestr(name[len(prefix):], source.read(name))
        return target
