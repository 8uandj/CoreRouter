"""Lazy JO-VPPM DRL model adapter for FastAPI inference."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from src.ai.heuristic import ActionChoice, get_resilience_safe_action
from src.core.state_manager import NetworkStateManager

logger = logging.getLogger("DGRLAgent")


DEFAULT_MODEL_PATH = os.getenv(
    "JO_VPPM_MODEL_PATH",
    "results/models/v10/dgrl_v10_final_vietnam.zip",
)
ENABLE_INPROCESS_MODEL = os.getenv("JO_VPPM_ENABLE_MODEL", "0") == "1"


@dataclass
class DGRLDecision:
    choice: ActionChoice
    model_loaded: bool
    fallback_reason: Optional[str] = None


class DGRLAgent:
    """Small wrapper that keeps ML dependencies optional for the backend."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH) -> None:
        self.model_path = model_path
        self._model: Any = None
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

            self._model = MaskablePPO.load(self.model_path, device="cpu")
            logger.info("Loaded JO-VPPM model from %s", self.model_path)
        except Exception as exc:
            self._load_error = f"model_load_failed:{exc}"
            logger.warning("Could not load JO-VPPM model: %s", exc)
            self._model = None
        return self._model

    def get_action(self, state_manager: NetworkStateManager, request: Any) -> DGRLDecision:
        """Return a DRL action, falling back to safe search if needed."""
        model = self._load_model()
        if model is None:
            snap = state_manager.snapshot()
            return DGRLDecision(
                choice=get_resilience_safe_action(snap, request),
                model_loaded=False,
                fallback_reason=self._load_error or "model_unavailable",
            )

        try:
            obs = state_manager.to_observation(request)[None, :]
            masks = state_manager.action_mask(request)[None, :]
            action, _ = model.predict(obs, action_masks=masks, deterministic=True)
            action_arr = np.asarray(action).reshape(-1)
            return DGRLDecision(
                choice=ActionChoice(
                    v_place=int(action_arr[0]),
                    v_route=int(action_arr[1]),
                    reason="maskableppo_gnn_policy",
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
