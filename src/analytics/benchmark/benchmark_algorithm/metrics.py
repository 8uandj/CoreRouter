from __future__ import annotations

from dataclasses import dataclass, field, asdict
from statistics import mean, pstdev
from typing import Dict, List

import numpy as np


@dataclass
class RunMetrics:
    algorithm: str
    scenario: str
    topology: str
    seed: int
    acceptance: List[bool] = field(default_factory=list)
    msd_violations: List[bool] = field(default_factory=list)
    latencies_ms: List[float] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    sla_violations: List[bool] = field(default_factory=list)
    evacuation_hits: List[bool] = field(default_factory=list)
    queue_latencies_ms: List[float] = field(default_factory=list)
    prop_latencies_ms: List[float] = field(default_factory=list)
    srv6_latencies_ms: List[float] = field(default_factory=list)

    @property
    def requests(self) -> int:
        return len(self.acceptance)

    @property
    def acc_rate(self) -> float:
        return float(np.mean(self.acceptance) * 100.0) if self.acceptance else 0.0

    @property
    def msd_rate(self) -> float:
        return float(np.mean(self.msd_violations) * 100.0) if self.msd_violations else 0.0

    @property
    def avg_lat(self) -> float:
        return float(np.mean(self.latencies_ms)) if self.latencies_ms else 0.0

    @property
    def p95_lat(self) -> float:
        return float(np.percentile(self.latencies_ms, 95)) if self.latencies_ms else 0.0

    @property
    def sla_rate(self) -> float:
        return float(np.mean(self.sla_violations) * 100.0) if self.sla_violations else 0.0

    @property
    def evac_rate(self) -> float:
        return float(np.mean(self.evacuation_hits) * 100.0) if self.evacuation_hits else 0.0

    @property
    def avg_reward(self) -> float:
        return float(np.mean(self.rewards)) if self.rewards else 0.0

    @property
    def avg_queue_lat(self) -> float:
        return float(np.mean(self.queue_latencies_ms)) if self.queue_latencies_ms else 0.0

    def rolling_acceptance(self, window: int = 200) -> np.ndarray:
        if not self.acceptance:
            return np.array([])
        arr = np.array(self.acceptance, dtype=float)
        if len(arr) < window:
            return np.array([self.acc_rate] * len(arr))
        ret = np.cumsum(arr)
        ret[window:] = ret[window:] - ret[:-window]
        return (ret[window - 1:] / window) * 100.0

    def collect(self, info: dict, reward: float) -> None:
        if info.get("skipped", False):
            return
        accepted = bool(info.get("accepted", False))
        self.acceptance.append(accepted)
        self.msd_violations.append(bool(info.get("admitted_msd_violation", False)))
        self.rewards.append(float(reward))
        self.evacuation_hits.append(bool(info.get("evacuation_hit", False)))
        if accepted:
            lat = float(info.get("total_latency_ms", 0.0))
            self.latencies_ms.append(lat)
            self.queue_latencies_ms.append(float(info.get("queue_latency_ms", 0.0)))
            self.prop_latencies_ms.append(float(info.get("prop_latency_ms", 0.0)))
            self.srv6_latencies_ms.append(float(info.get("srv6_latency_ms", 0.0)))
            threshold = float(info.get("latency_threshold_ms", 80.0))
            self.sla_violations.append(lat > threshold)

    def as_summary(self) -> Dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "topology": self.topology,
            "scenario": self.scenario,
            "seed": self.seed,
            "requests": self.requests,
            "acceptance_rate": self.acc_rate,
            "msd_violation_rate": self.msd_rate,
            "sla_violation_rate": self.sla_rate,
            "avg_latency_ms": self.avg_lat,
            "p95_latency_ms": self.p95_lat,
            "avg_queue_latency_ms": self.avg_queue_lat,
            "evacuation_hit_rate": self.evac_rate,
            "avg_reward": self.avg_reward,
        }


def aggregate_runs(runs: List[RunMetrics]) -> Dict[str, object]:
    if not runs:
        return {}
    keys = [
        ("acceptance_rate", "acc_rate"),
        ("msd_violation_rate", "msd_rate"),
        ("sla_violation_rate", "sla_rate"),
        ("avg_latency_ms", "avg_lat"),
        ("p95_latency_ms", "p95_lat"),
        ("avg_queue_latency_ms", "avg_queue_lat"),
        ("evacuation_hit_rate", "evac_rate"),
        ("avg_reward", "avg_reward"),
    ]
    out: Dict[str, object] = {
        "algorithm": runs[0].algorithm,
        "topology": runs[0].topology,
        "scenario": runs[0].scenario,
        "seeds": len(runs),
        "requests_mean": mean([r.requests for r in runs]),
    }
    for label, attr in keys:
        vals = [float(getattr(r, attr)) for r in runs]
        out[f"{label}_mean"] = mean(vals)
        out[f"{label}_std"] = pstdev(vals) if len(vals) > 1 else 0.0
    return out

