"""Regression checks for inference from the recovered legacy v11 policy."""

from pathlib import Path
from importlib import import_module
import sys
import types

import numpy as np
import pytest

from src.ai.dgrl_agent import DGRLAgent


MODEL = Path("results/models/v11/dgrl_v11_final_vietnam.zip")
NORMALIZER = Path("results/models/v11/vec_normalize_v11_vietnam.pkl")


def test_legacy_checkpoint_predicts_under_pair_mask():
    agent = DGRLAgent(str(MODEL))
    agent.scaler_path = str(NORMALIZER)
    model = agent._load_model()

    assert model is not None
    assert model.action_space.n == 100
    assert agent._scaler is not None
    obs = agent._scaler.normalize_obs(np.zeros((1, 73), dtype=np.float32))
    mask = np.zeros((1, 100), dtype=bool)
    mask[0, 42] = True
    action, _ = model.predict(obs, action_masks=mask, deterministic=True)
    assert int(np.asarray(action).reshape(-1)[0]) == 42


def test_status_reports_legacy_source_encoding(monkeypatch):
    stub = types.ModuleType("src.portal.backend.app.containers.service_container")
    stub.container = object()
    monkeypatch.setitem(sys.modules, stub.__name__, stub)
    ai = import_module("src.portal.backend.app.routers.ai")
    agent = DGRLAgent(str(MODEL))
    agent.scaler_path = str(NORMALIZER)
    monkeypatch.setattr(ai, "get_dgrl_agent", lambda: agent)

    status = ai.get_ai_status()

    assert status["model_loaded"] is True
    assert status["action_encoding"] == "factorized_2n_to_flat_n2"


def test_missing_normalizer_never_exposes_loaded_policy(tmp_path):
    agent = DGRLAgent(str(MODEL))
    agent.scaler_path = str(tmp_path / "missing.pkl")

    with pytest.raises(RuntimeError, match="normalizer_not_found"):
        agent._load_model()

    assert agent._model is None
    with pytest.raises(RuntimeError, match="normalizer_not_found"):
        agent._load_model()
