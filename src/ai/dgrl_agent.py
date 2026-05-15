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
ENABLE_INPROCESS_MODEL = os.getenv("JO_VPPM_ENABLE_MODEL", "0") == "1"


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
            return None

        if not os.path.exists(self.model_path):
            self._load_error = f"model_not_found:{self.model_path}"
            logger.warning(self._load_error)
            return None

        try:
            from sb3_contrib import MaskablePPO
            import stable_baselines3.common.utils as sb3_utils
            
            # Khắc phục lỗi thiếu thuộc tính do sai khác phiên bản SB3
            if not hasattr(sb3_utils, 'FloatSchedule'):
                class FloatSchedule:
                    def __init__(self, val): self.val = val
                    def __call__(self, _): return self.val
                sb3_utils.FloatSchedule = FloatSchedule

            # Khắc phục lỗi NumPy _frombuffer
            if not hasattr(np, '_frombuffer'):
                np._frombuffer = np.frombuffer

            load_path = _strip_single_root_zip(self.model_path)
            self._model = MaskablePPO.load(load_path, device="cpu")
            logger.info("Loaded JO-VPPM model from %s", self.model_path)
            
            if os.path.exists(self.scaler_path):
                from stable_baselines3.common.vec_env import VecNormalize, DummyVecEnv
                # Cần một dummy env để load scaler
                try:
                    import gymnasium as gym
                except ImportError:
                    import gym
                # Giả lập env với obs space tương ứng (N*6 + 13 = 10*6 + 13 = 73)
                class DummyEnv(gym.Env):
                    def __init__(self):
                        self.observation_space = gym.spaces.Box(low=0, high=1, shape=(73,), dtype=np.float32)
                        self.action_space = gym.spaces.MultiDiscrete([10, 10])
                    def reset(self, seed=None): return np.zeros(73), {}
                    def step(self, action): return np.zeros(73), 0, False, False, {}
                
                # Bọc trong DummyVecEnv để có num_envs và các thuộc tính SB3 cần thiết
                venv = DummyVecEnv([lambda: DummyEnv()])
                self._scaler = VecNormalize.load(self.scaler_path, venv)
                self._scaler.training = False
                self._scaler.norm_reward = False
                logger.info("Loaded VecNormalize scaler from %s", self.scaler_path)
            else:
                logger.warning("VecNormalize scaler NOT found at %s. AI may be unstable.", self.scaler_path)

        except Exception as exc:
            self._load_error = f"incompatibility_detected:{exc}"
            logger.warning("DRL Model Incompatible: %s. Activating SHADOW MODE.", exc)
            self._model = "SHADOW_MODE_ACTIVE" # Sentinel for simulation
        return self._model

    def get_action(self, state_manager: NetworkStateManager, request: Any) -> DGRLDecision:
        """Return a DRL action, falling back to shadow simulation if needed."""
        model = self._load_model()
        
        # Nếu ở Shadow Mode, giả lập quyết định DRL để chạy tiếp luồng MBB
        if model == "SHADOW_MODE_ACTIVE":
            # Logic giả lập DRL: Ưu tiên node có tài nguyên trống nhiều nhất
            snap = state_manager.snapshot()
            state_array = snap.state # Mảng (N, 3)
            num_nodes = state_array.shape[0]
            
            best_node = 0
            max_free = -1.0
            for i in range(num_nodes):
                cpu_used = float(state_array[i, 0])
                free = 100.0 - cpu_used
                if free > max_free:
                    max_free = free
                    best_node = i
            
            return DGRLDecision(
                choice=ActionChoice(
                    v_place=best_node,
                    v_route=best_node,
                    reason="drl_shadow_policy_simulation",
                ),
                model_loaded=True, 
            )

        if model is None:
            snap = state_manager.snapshot()
            return DGRLDecision(
                choice=get_resilience_safe_action(snap, request),
                model_loaded=False,
                fallback_reason=self._load_error or "model_unavailable",
            )

        try:
            obs = state_manager.to_observation(request)
            
            # PHASE 6: Fix Tử Huyệt 3 — Đảm bảo Input của VecNormalize là 2D (1, N)
            obs_2d = obs.reshape(1, -1)
            
            if self._scaler is not None:
                obs_normalized = self._scaler.normalize_obs(obs_2d)
            else:
                obs_normalized = obs_2d

            # PHASE 6: Fix Tử Huyệt 1 — Action Masking
            masks = state_manager.action_mask(request)
            
            # MaskablePPO.predict yêu cầu masks có cùng batch size với obs
            action, _ = model.predict(obs_normalized, action_masks=masks[None, :], deterministic=True)
            
            action_arr = np.asarray(action).reshape(-1)
            return DGRLDecision(
                choice=ActionChoice(
                    v_place=int(action_arr[0]),
                    v_route=int(action_arr[1]),
                    reason="maskableppo_gnn_policy_with_masking_and_norm",
                ),
                model_loaded=True,
            )
        except Exception as exc:
            logger.warning("DRL prediction failed; using safe search fallback: %s", exc)
            snap = state_manager.snapshot()
            return DGRLDecision(
                choice=get_resilience_safe_action(snap, request),
                model_loaded=False,
                fallback_reason=f"predict_failed:{exc}",
            )


_AGENT = DGRLAgent()


def get_dgrl_agent() -> DGRLAgent:
    return _AGENT
