from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

import numpy as np
import requests
import torch
import torch.nn as nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Forecaster")

THRESHOLD = float(os.getenv("JO_VPPM_FORECAST_PPS_THRESHOLD", "800"))
FASTAPI_URL = "http://127.0.0.1:8000/api/orchestrate/alert"

class BiGRUForecaster(nn.Module):
    def __init__(self, input_dim=1, hidden_dim=16, output_dim=1, num_layers=1):
        super(BiGRUForecaster, self).__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, num_layers, batch_first=True, bidirectional=True)
        self.fc = nn.Linear(hidden_dim * 2, output_dim)

    def forward(self, x):
        out, _ = self.gru(x)
        out = self.fc(out[:, -1, :])
        return out


@dataclass(frozen=True)
class ForecastDecision:
    node_id: int
    current_pps: float
    predicted_pps: float
    alert: bool
    reason: str


class TrafficForecastService:
    """Online Bi-GRU forecasting adapter used by the backend closed loop.

    If a trained checkpoint is provided through JO_VPPM_BIGRU_MODEL_PATH, it is
    loaded. Otherwise, the service still exposes the Bi-GRU integration point and
    uses a deterministic trend extrapolator so alert behavior is stable.
    """

    def __init__(self, window_size: int = 5, threshold: float = THRESHOLD) -> None:
        self.window_size = int(window_size)
        self.threshold = float(threshold)
        self._series: Dict[int, Deque[float]] = defaultdict(lambda: deque(maxlen=self.window_size))
        self._alerts: Dict[int, ForecastDecision] = {}
        self._model: Optional[BiGRUForecaster] = None
        self._model_loaded = False
        self._load_model()

    @property
    def model_loaded(self) -> bool:
        return self._model_loaded

    def _load_model(self) -> None:
        model_path = os.getenv("JO_VPPM_BIGRU_MODEL_PATH", "").strip()
        if not model_path:
            return
        try:
            model = BiGRUForecaster()
            payload = torch.load(model_path, map_location="cpu")
            state = payload.get("state_dict", payload) if isinstance(payload, dict) else payload
            model.load_state_dict(state)
            model.eval()
            self._model = model
            self._model_loaded = True
            logger.info("Loaded Bi-GRU forecaster from %s", model_path)
        except Exception as exc:
            logger.warning("Bi-GRU checkpoint load failed, using deterministic trend forecast: %s", exc)

    def observe(self, node_id: int, pps: float) -> ForecastDecision:
        node = int(node_id)
        value = float(pps)
        series = self._series[node]
        series.append(value)
        values = list(series)

        if len(values) >= self.window_size and self._model is not None:
            with torch.no_grad():
                tensor = torch.tensor(values[-self.window_size:], dtype=torch.float32).view(1, self.window_size, 1)
                predicted = float(self._model(tensor).item())
            reason = "bigru_checkpoint"
        elif len(values) >= 2:
            # Stable fallback: forecast one step ahead from the recent slope.
            slope = values[-1] - values[-2]
            predicted = max(0.0, values[-1] + slope)
            reason = "deterministic_trend"
        else:
            predicted = value
            reason = "single_sample"

        alert = predicted >= self.threshold
        decision = ForecastDecision(
            node_id=node,
            current_pps=value,
            predicted_pps=predicted,
            alert=alert,
            reason=reason,
        )
        self._alerts[node] = decision
        return decision

    def status(self) -> Dict[str, object]:
        return {
            "threshold": self.threshold,
            "window_size": self.window_size,
            "model_loaded": self.model_loaded,
            "alerts": {
                node: {
                    "current_pps": d.current_pps,
                    "predicted_pps": d.predicted_pps,
                    "alert": d.alert,
                    "reason": d.reason,
                }
                for node, d in sorted(self._alerts.items())
            },
        }


_FORECAST_SERVICE = TrafficForecastService()


def get_forecast_service() -> TrafficForecastService:
    return _FORECAST_SERVICE

def run_analytics_pipeline():
    logger.info("Initializing Bi-GRU Proactive Forecaster")
    
    model = BiGRUForecaster()
    model.eval()
    
    sequence = [300.0, 450.0, 500.0, 680.0, 750.0]
    
    for step in range(5):
        time.sleep(1)
        input_tensor = torch.tensor(sequence, dtype=torch.float32).view(1, 5, 1)
        
        with torch.no_grad():
            pred = model(input_tensor).item()
            
        logger.info(f"[t={step}s] Current: {int(sequence[-1])} pps -> Pred t+1: {int(pred)} pps")
        
        if pred > THRESHOLD:
            logger.warning("Traffic threshold breach predicted. Activating proactive migration.")
            try:
                requests.post(FASTAPI_URL, params={"alert": "true"}, timeout=2)
                logger.info("Migration command sent to orchestrator.")
            except Exception:
                logger.error("Backend unreachable for migration command.")
            break
            
        new_val = sequence[-1] + np.random.randint(20, 80)
        sequence.append(float(new_val))
        sequence.pop(0)

if __name__ == "__main__":
    run_analytics_pipeline()
