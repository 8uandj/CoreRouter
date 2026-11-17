"""Lazy JO-VPPM DRL model adapter for FastAPI inference."""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from zipfile import ZipFile

import numpy as np
import sys
import time
from dataclasses import field

# RÀ SOÁT: Sửa lỗi "No module named 'numpy._core'" do mô hình được lưu bằng NumPy 2.0+
# nhưng hệ thống đang chạy NumPy 1.x (Python 3.8).
if 'numpy._core' not in sys.modules:
    import types
    # Tạo một module giả lập cho numpy._core
    core = types.ModuleType('numpy._core')
    core.numeric = np
    core.multiarray = np
    core.umath = np
    core.fixed_tuple = np.recarray # Đôi khi cần cho pickle
    sys.modules['numpy._core'] = core
    sys.modules['numpy._core.numeric'] = np
    sys.modules['numpy._core.multiarray'] = np
    sys.modules['numpy._core.umath'] = np

from src.ai.heuristic import ActionChoice, get_resilience_safe_action
from src.core.state_manager import NetworkStateManager

logger = logging.getLogger("DGRLAgent")


DEFAULT_MODEL_PATH = os.getenv(
    "JO_VPPM_MODEL_PATH",
    "results/models/v11/dgrl_v11_final_vietnam.zip",
)
ENABLE_INPROCESS_MODEL = os.getenv("JO_VPPM_ENABLE_MODEL", "1") == "1"
REQUIRE_REAL_MODEL = os.getenv("JO_VPPM_REQUIRE_MODEL", "1") == "1"


def _infer_scaler_path(model_path: str) -> str:
    """Infer the matching VecNormalize artifact for a JO-VPPM checkpoint."""
    explicit_path = os.getenv("JO_VPPM_SCALER_PATH")
    if explicit_path:
        return explicit_path

    path = Path(model_path)
    stem = path.name
    if stem.startswith("dgrl_") and stem.endswith(".zip"):
        parts = stem[:-4].split("_")
        if len(parts) >= 4 and parts[0] == "dgrl" and parts[2] == "final":
            version = parts[1]
            topology = "_".join(parts[3:])
            return str(path.with_name(f"vec_normalize_{version}_{topology}.pkl"))

    return str(path.with_name("vec_normalize_v11_vietnam.pkl"))


def decode_flat_action(action: Any, num_nodes: int) -> tuple[int, int]:
    """Decode the training environment's Discrete(N*N) pair action."""
    try:
        values = np.asarray(action).reshape(-1)
        if values.size != 1:
            raise ValueError
        raw = values[0].item() if hasattr(values[0], "item") else values[0]
        flat = int(raw)
        if flat != raw or num_nodes <= 0 or not 0 <= flat < num_nodes * num_nodes:
            raise ValueError
        return flat // num_nodes, flat % num_nodes
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid flat placement/routing action: {action!r}") from exc


class NpzVecNormalize:
    """Small inference-only VecNormalize reader for cross-version scaler stats."""

    def __init__(self, path: str) -> None:
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


def _strip_single_root_zip(zip_path: str) -> str:
    """Return an SB3-compatible zip path, flattening single-root archives if needed."""
    with ZipFile(zip_path, "r") as source:
        names = [name for name in source.namelist() if not name.endswith("/")]
        if "data" in names:
            return zip_path

        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            return zip_path

        root = next(iter(roots))
        if f"{root}/data" not in names:
            return zip_path

        source_stat = os.stat(zip_path)
        cache_dir = Path(tempfile.gettempdir()) / "corerouter_sb3_models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        flattened = cache_dir / (
            f"{Path(zip_path).stem}-{source_stat.st_mtime_ns}-{source_stat.st_size}.zip"
        )
        if flattened.exists():
            return str(flattened)

        with ZipFile(flattened, "w") as target:
            prefix = f"{root}/"
            for name in names:
                if not name.startswith(prefix):
                    continue
                target.writestr(name[len(prefix):], source.read(name))

    logger.info("Normalized nested SB3 archive %s -> %s", zip_path, flattened)
    return str(flattened)


@dataclass
class DGRLDecision:
    choice: ActionChoice
    model_loaded: bool
    fallback_reason: Optional[str] = None
    timings_ms: dict[str, float] = field(default_factory=dict)


class DGRLAgent:
    """Small wrapper that keeps ML dependencies optional for the backend."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH) -> None:
        self.model_path = model_path
        self.scaler_path = _infer_scaler_path(model_path)
        self._model: Any = None
        self._scaler: Any = None
        self._load_error: Optional[str] = None
        self._load_attempted = False

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _load_model(self) -> Any:
        if self._load_attempted:
            return self._model
        self._load_attempted = True

        if not ENABLE_INPROCESS_MODEL:
            self._load_error = "model_loading_disabled:set_JO_VPPM_ENABLE_MODEL=1"
            logger.warning(self._load_error)
            if REQUIRE_REAL_MODEL:
                raise RuntimeError(self._load_error)
            return None

        if not os.path.exists(self.model_path):
            self._load_error = f"model_not_found:{self.model_path}"
            logger.warning(self._load_error)
            if REQUIRE_REAL_MODEL:
                raise FileNotFoundError(self._load_error)
            return None

        try:
            from sb3_contrib import MaskablePPO
            import stable_baselines3.common.utils as sb3_utils
            import gymnasium as gym

            from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
            from src.orchestration.jo_vdpr.topology import DEFAULT_TOPO
            
            # Khắc phục lỗi thiếu thuộc tính do sai khác phiên bản SB3
            if not hasattr(sb3_utils, 'FloatSchedule'):
                class FloatSchedule:
                    def __init__(self, val): self.val = val
                    def __call__(self, _): return self.val
                sb3_utils.FloatSchedule = FloatSchedule
            if not hasattr(sb3_utils, 'ConstantSchedule'):
                class ConstantSchedule:
                    def __init__(self, val): self.val = val
                    def __call__(self, _): return self.val
                sb3_utils.ConstantSchedule = ConstantSchedule

            # Khắc phục lỗi NumPy _frombuffer
            if not hasattr(np, '_frombuffer'):
                np._frombuffer = np.frombuffer

            load_path = _strip_single_root_zip(self.model_path)
            obs_space = gym.spaces.Box(low=0, high=1, shape=(73,), dtype=np.float32)
            action_space = gym.spaces.Discrete(10 * 10)
            policy_kwargs = dict(
                num_nodes=DEFAULT_TOPO.num_nodes,
                adj_matrix=DEFAULT_TOPO.adj_matrix,
                gat_hidden=64,
                gat_heads=4,
                features_dim=256,
            )
            custom_objects = {
                "policy_class": GNNActorCriticPolicy,
                "policy_kwargs": policy_kwargs,
                "observation_space": obs_space,
                "action_space": action_space,
                "learning_rate": 0.0003,
                "lr_schedule": lambda _: 0.0003,
                "clip_range": lambda _: 0.2,
                "_last_obs": None,
                "_last_episode_starts": None,
                "_last_original_obs": None,
                "ep_info_buffer": [],
            }
            self._model = MaskablePPO.load(load_path, device="cpu", custom_objects=custom_objects)
            logger.info("Loaded JO-VPPM model from %s", self.model_path)
            
            if os.path.exists(self.scaler_path):
                try:
                    from stable_baselines3.common.vec_env import VecNormalize, DummyVecEnv
                    # Cần một dummy env để load scaler
                    # Giả lập env với obs space tương ứng (N*6 + 13 = 10*6 + 13 = 73)
                    class DummyEnv(gym.Env):
                        def __init__(self):
                            self.observation_space = gym.spaces.Box(low=0, high=1, shape=(73,), dtype=np.float32)
                            self.action_space = gym.spaces.Discrete(10 * 10)
                        def reset(self, seed=None): return np.zeros(73), {}
                        def step(self, action): return np.zeros(73), 0, False, False, {}
                    
                    # Bọc trong DummyVecEnv để có num_envs và các thuộc tính SB3 cần thiết
                    venv = DummyVecEnv([lambda: DummyEnv()])
                    self._scaler = VecNormalize.load(self.scaler_path, venv)
                    self._scaler.training = False
                    self._scaler.norm_reward = False
                    logger.info("Loaded VecNormalize scaler from %s", self.scaler_path)
                except Exception as exc:
                    npz_path = str(Path(self.scaler_path).with_suffix(".npz"))
                    if os.path.exists(npz_path):
                        self._scaler = NpzVecNormalize(npz_path)
                        logger.info("Loaded VecNormalize stats from %s after pickle failure: %s", npz_path, exc)
                    else:
                        self._scaler = None
                        logger.warning("VecNormalize scaler load failed: %s", exc)
            else:
                raise FileNotFoundError(f"normalizer_not_found:{self.scaler_path}")
            if self._scaler is None:
                raise RuntimeError("normalizer_unavailable: checkpoint requires its matching observation statistics")

        except Exception as exc:
            self._load_error = f"incompatibility_detected:{exc}"
            if REQUIRE_REAL_MODEL:
                logger.exception("DRL model is required but failed to load.")
                raise RuntimeError(self._load_error) from exc
            logger.warning("DRL Model Unavailable: %s", exc)
            self._model = None
        return self._model

    def get_action(self, state_manager: NetworkStateManager, request: Any) -> DGRLDecision:
        """Return a checkpoint action or an explicit safe-search fallback."""
        total_start = time.perf_counter()
        model = self._load_model()

        if model is None:
            snap = state_manager.snapshot()
            return DGRLDecision(
                choice=get_resilience_safe_action(snap, request),
                model_loaded=False,
                fallback_reason=self._load_error or "model_unavailable",
                timings_ms={"total_policy_ms": (time.perf_counter() - total_start) * 1000.0},
            )

        try:
            state_start = time.perf_counter()
            obs = state_manager.to_observation(request)
            state_ms = (time.perf_counter() - state_start) * 1000.0

            mask_start = time.perf_counter()
            masks = np.asarray(state_manager.action_mask(request), dtype=bool)
            mask_ms = (time.perf_counter() - mask_start) * 1000.0
            n = state_manager.num_nodes
            if masks.size != n * n or not masks.any():
                snap = state_manager.snapshot()
                return DGRLDecision(
                    choice=get_resilience_safe_action(snap, request),
                    model_loaded=False,
                    fallback_reason="empty_action_mask",
                    timings_ms={"state_construction_ms": state_ms, "mask_construction_ms": mask_ms},
                )

            if n != 10 or obs.size != 73:
                snap = state_manager.snapshot()
                return DGRLDecision(
                    choice=get_resilience_safe_action(snap, request),
                    model_loaded=False,
                    fallback_reason=f"checkpoint_space_mismatch:nodes={n},obs={obs.size}",
                    timings_ms={"state_construction_ms": state_ms, "mask_construction_ms": mask_ms},
                )
            
            # PHASE 6: Fix Tử Huyệt 3 — Đảm bảo Input của VecNormalize là 2D (1, N)
            obs_2d = obs.reshape(1, -1)
            
            normalization_start = time.perf_counter()
            if self._scaler is not None:
                obs_normalized = self._scaler.normalize_obs(obs_2d)
            else:
                obs_normalized = obs_2d
            normalization_ms = (time.perf_counter() - normalization_start) * 1000.0

            # PHASE 6: Fix Tử Huyệt 1 — Action Masking
            # MaskablePPO.predict yêu cầu masks có cùng batch size với obs
            inference_start = time.perf_counter()
            action, _ = model.predict(obs_normalized, action_masks=masks[None, :], deterministic=True)
            inference_ms = (time.perf_counter() - inference_start) * 1000.0
            
            v_place, v_route = decode_flat_action(action, n)
            return DGRLDecision(
                choice=ActionChoice(
                    v_place=v_place,
                    v_route=v_route,
                    reason="maskableppo_gnn_policy_with_flat_pair_mask_and_norm",
                ),
                model_loaded=True,
                timings_ms={
                    "state_construction_ms": state_ms,
                    "mask_construction_ms": mask_ms,
                    "normalization_ms": normalization_ms,
                    "policy_inference_ms": inference_ms,
                    "total_policy_ms": (time.perf_counter() - total_start) * 1000.0,
                },
            )
        except Exception as exc:
            logger.warning("DRL prediction failed; using safe search fallback: %s", exc)
            snap = state_manager.snapshot()
            return DGRLDecision(
                choice=get_resilience_safe_action(snap, request),
                model_loaded=False,
                fallback_reason=f"predict_failed:{exc}",
                timings_ms={"total_policy_ms": (time.perf_counter() - total_start) * 1000.0},
            )


_AGENT = DGRLAgent()


def get_dgrl_agent() -> DGRLAgent:
    return _AGENT
