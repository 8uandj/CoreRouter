from __future__ import annotations

from dataclasses import dataclass, field, asdict
import hashlib
import json
import time
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
    candidate_msd_violations: List[bool] = field(default_factory=list)
    cpu_violations: List[bool] = field(default_factory=list)
    ram_violations: List[bool] = field(default_factory=list)
    bw_violations: List[bool] = field(default_factory=list)
    admitted_cpu_violations: List[bool] = field(default_factory=list)
    admitted_ram_violations: List[bool] = field(default_factory=list)
    admitted_bw_violations: List[bool] = field(default_factory=list)
    admitted_hard_violations: List[bool] = field(default_factory=list)
    candidate_hard_violations: List[bool] = field(default_factory=list)
    safe_acceptance: List[bool] = field(default_factory=list)
    rejected_by_cpu: List[bool] = field(default_factory=list)
    rejected_by_ram: List[bool] = field(default_factory=list)
    rejected_by_msd: List[bool] = field(default_factory=list)
    rejected_by_bw: List[bool] = field(default_factory=list)
    rejected_by_other: List[bool] = field(default_factory=list)
    latencies_ms: List[float] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    sla_violations: List[bool] = field(default_factory=list)
    evacuation_hits: List[bool] = field(default_factory=list)
    queue_latencies_ms: List[float] = field(default_factory=list)
    prop_latencies_ms: List[float] = field(default_factory=list)
    srv6_latencies_ms: List[float] = field(default_factory=list)
    trace_records: List[dict] = field(default_factory=list)
    mask_candidate_counts: List[int] = field(default_factory=list)
    mask_total_candidates: List[int] = field(default_factory=list)
    mask_empty_steps: List[bool] = field(default_factory=list)
    decision_latency_ms: List[float] = field(default_factory=list)
    component_latencies_ms: Dict[str, List[float]] = field(default_factory=dict)
    _run_started_at: float | None = field(default=None, repr=False)
    run_wall_time_s: float = 0.0

    def start_clock(self) -> None:
        self._run_started_at = time.perf_counter()

    def stop_clock(self) -> None:
        if self._run_started_at is not None:
            self.run_wall_time_s = max(0.0, time.perf_counter() - self._run_started_at)
            self._run_started_at = None

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
        if "trace_request" in info:
            self.trace_records.append(dict(info["trace_request"]))
        if info.get("skipped", False):
            return
        accepted = bool(info.get("accepted", False))
        for key, value in info.get("decision_components_ms", {}).items():
            self.component_latencies_ms.setdefault(str(key), []).append(float(value))
        for key in ("state_construction_ms", "admission_validation_ms", "environment_step_ms"):
            if key in info:
                self.component_latencies_ms.setdefault(key, []).append(float(info[key]))
        if "decision_latency_ms" in info:
            self.decision_latency_ms.append(float(info["decision_latency_ms"]))
        elif "environment_step_ms" in info:
            self.decision_latency_ms.append(float(info["environment_step_ms"]))
        if "mask_candidate_count" in info:
            self.mask_candidate_counts.append(int(info["mask_candidate_count"]))
            self.mask_total_candidates.append(int(info["mask_total_candidates"]))
            self.mask_empty_steps.append(bool(info.get("mask_empty", False)))
        self.acceptance.append(accepted)
        self.msd_violations.append(bool(info.get("admitted_msd_violation", False)))
        self.candidate_msd_violations.append(bool(info.get("msd_violation", False)))
        self.cpu_violations.append(bool(info.get("cpu_violation", False)))
        self.ram_violations.append(bool(info.get("ram_violation", False)))
        self.bw_violations.append(bool(info.get("bw_violation", False)))
        admitted_cpu = bool(info.get("admitted_cpu_violation", False))
        admitted_ram = bool(info.get("admitted_ram_violation", False))
        admitted_bw = bool(info.get("admitted_bw_violation", False))
        self.admitted_cpu_violations.append(admitted_cpu)
        self.admitted_ram_violations.append(admitted_ram)
        self.admitted_bw_violations.append(admitted_bw)
        admitted_msd = bool(info.get("admitted_msd_violation", False))
        self.admitted_hard_violations.append(admitted_cpu or admitted_ram or admitted_bw or admitted_msd)
        candidate_cpu = bool(info.get("cpu_violation", False))
        candidate_ram = bool(info.get("ram_violation", False))
        candidate_msd = bool(info.get("msd_violation", False))
        candidate_bw = bool(info.get("bw_violation", False))
        self.candidate_hard_violations.append(candidate_cpu or candidate_ram or candidate_msd or candidate_bw)
        self.safe_acceptance.append(accepted and not (admitted_cpu or admitted_ram or admitted_bw or admitted_msd))
        reason = info.get("rejection_reason") if not accepted else None
        self.rejected_by_cpu.append(reason == "cpu")
        self.rejected_by_ram.append(reason == "ram")
        self.rejected_by_msd.append(reason == "msd")
        self.rejected_by_bw.append(reason == "bw")
        self.rejected_by_other.append((not accepted) and reason not in {"cpu", "ram", "msd", "bw"})
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
        trace_hash = hashlib.sha256(
            json.dumps(self.trace_records, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        result = {
            "algorithm": self.algorithm,
            "topology": self.topology,
            "scenario": self.scenario,
            "seed": self.seed,
            "requests": self.requests,
            "acceptance_rate": self.acc_rate,
            "safe_acceptance_rate": float(np.mean(self.safe_acceptance) * 100.0) if self.safe_acceptance else 0.0,
            "candidate_hard_infeasible_rate": float(np.mean(self.candidate_hard_violations) * 100.0) if self.candidate_hard_violations else 0.0,
            "rejection_cpu_rate": float(np.mean(self.rejected_by_cpu) * 100.0) if self.rejected_by_cpu else 0.0,
            "rejection_ram_rate": float(np.mean(self.rejected_by_ram) * 100.0) if self.rejected_by_ram else 0.0,
            "rejection_msd_rate": float(np.mean(self.rejected_by_msd) * 100.0) if self.rejected_by_msd else 0.0,
            "rejection_bw_rate": float(np.mean(self.rejected_by_bw) * 100.0) if self.rejected_by_bw else 0.0,
            "rejection_other_rate": float(np.mean(self.rejected_by_other) * 100.0) if self.rejected_by_other else 0.0,
            "msd_violation_rate": self.msd_rate,
            "candidate_cpu_violation_rate": float(np.mean(self.cpu_violations) * 100.0) if self.cpu_violations else 0.0,
            "candidate_ram_violation_rate": float(np.mean(self.ram_violations) * 100.0) if self.ram_violations else 0.0,
            "candidate_msd_violation_rate": float(np.mean(self.candidate_msd_violations) * 100.0) if self.candidate_msd_violations else 0.0,
            "candidate_bw_violation_rate": float(np.mean(self.bw_violations) * 100.0) if self.bw_violations else 0.0,
            "admitted_cpu_violation_rate": float(np.mean(self.admitted_cpu_violations) * 100.0) if self.admitted_cpu_violations else 0.0,
            "admitted_ram_violation_rate": float(np.mean(self.admitted_ram_violations) * 100.0) if self.admitted_ram_violations else 0.0,
            "admitted_bw_violation_rate": float(np.mean(self.admitted_bw_violations) * 100.0) if self.admitted_bw_violations else 0.0,
            "admitted_hard_violation_rate": float(np.mean(self.admitted_hard_violations) * 100.0) if self.admitted_hard_violations else 0.0,
            "sla_violation_rate": self.sla_rate,
            "avg_latency_ms": self.avg_lat,
            "p95_latency_ms": self.p95_lat,
            "avg_queue_latency_ms": self.avg_queue_lat,
            "evacuation_hit_rate": self.evac_rate,
            "avg_reward": self.avg_reward,
            "trace_sha256": trace_hash,
            "trace_steps": len(self.trace_records),
            "mask_candidate_count_mean": float(np.mean(self.mask_candidate_counts)) if self.mask_candidate_counts else None,
            "mask_eliminated_candidate_rate": (
                float(np.mean([
                    1.0 - count / total if total else 0.0
                    for count, total in zip(self.mask_candidate_counts, self.mask_total_candidates)
                ]) * 100.0) if self.mask_candidate_counts else None
            ),
            "mask_empty_rate": float(np.mean(self.mask_empty_steps) * 100.0) if self.mask_empty_steps else None,
        }
        result["decision_latency_p50_ms"] = float(np.percentile(self.decision_latency_ms, 50)) if self.decision_latency_ms else 0.0
        result["decision_latency_p95_ms"] = float(np.percentile(self.decision_latency_ms, 95)) if self.decision_latency_ms else 0.0
        result["decision_latency_p99_ms"] = float(np.percentile(self.decision_latency_ms, 99)) if self.decision_latency_ms else 0.0
        result["run_wall_time_s"] = self.run_wall_time_s
        result["offered_decisions_per_s"] = self.requests / self.run_wall_time_s if self.run_wall_time_s > 0 else 0.0
        for component, values in self.component_latencies_ms.items():
            result[f"{component}_p50_ms"] = float(np.percentile(values, 50))
            result[f"{component}_p95_ms"] = float(np.percentile(values, 95))
            result[f"{component}_p99_ms"] = float(np.percentile(values, 99))
        return result


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
    all_decisions = [value for run in runs for value in run.decision_latency_ms]
    total_wall = sum(run.run_wall_time_s for run in runs)
    out["decision_latency_p50_ms"] = float(np.percentile(all_decisions, 50)) if all_decisions else 0.0
    out["decision_latency_p95_ms"] = float(np.percentile(all_decisions, 95)) if all_decisions else 0.0
    out["decision_latency_p99_ms"] = float(np.percentile(all_decisions, 99)) if all_decisions else 0.0
    out["run_wall_time_s"] = total_wall
    out["offered_decisions_per_s"] = sum(run.requests for run in runs) / total_wall if total_wall > 0 else 0.0
    component_names = {key for run in runs for key in run.component_latencies_ms}
    for component in component_names:
        values = [
            value for run in runs
            for value in run.component_latencies_ms.get(component, [])
        ]
        out[f"{component}_p50_ms"] = float(np.percentile(values, 50)) if values else 0.0
        out[f"{component}_p95_ms"] = float(np.percentile(values, 95)) if values else 0.0
        out[f"{component}_p99_ms"] = float(np.percentile(values, 99)) if values else 0.0
    return out

