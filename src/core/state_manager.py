"""Shared network state for Adaptive Hybrid Orchestration.

The backend uses this singleton as the source of truth for both routing
branches.  Heuristic and DRL decisions must reserve resources through the same
manager so the DRL agent never wakes up with a stale view of the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.orchestration.jo_vdpr.topology import TopologyManager


MAX_CPU: float = 100.0
MAX_RAM: float = 100.0
AI_ENGAGE_THRESHOLD: float = 0.45
AI_RELEASE_THRESHOLD: float = 0.35
ALERT_CPU_THRESHOLD: float = 0.80


@dataclass(frozen=True)
class HybridDecision:
    """Routing branch selected by the hysteresis gate."""

    mode: str
    reason: str
    global_utilization: float
    avg_cpu: float
    avg_msd_usage: float
    alert_flag: bool


class NetworkStateManager:
    """Thread-safe singleton state for the Vietnam backbone testbed."""

    def __init__(self, topology_name: str = "vietnam") -> None:
        self._lock = RLock()
        self.topology = TopologyManager(topology_name)
        self.num_nodes = self.topology.num_nodes
        self._state = np.zeros((self.num_nodes, 3), dtype=np.float32)
        self._forecast_alert = False
        self._mode = "heuristic"

    def reset(self) -> None:
        """Clear resource usage and return the hybrid gate to normal mode."""
        with self._lock:
            self._state = np.zeros((self.num_nodes, 3), dtype=np.float32)
            self._forecast_alert = False
            self._mode = "heuristic"

    def set_forecast_alert(self, alert_flag: bool) -> None:
        """Inject the Bi-GRU forecast signal or its simulation proxy."""
        with self._lock:
            self._forecast_alert = bool(alert_flag)

    def snapshot(self) -> Dict[str, Any]:
        """Return an immutable-ish dict snapshot for routing decisions."""
        with self._lock:
            state = self._state.copy()
            avg_cpu = float(np.mean(state[:, 0] / MAX_CPU))
            avg_msd_usage = float(np.mean(state[:, 2] / self.topology.msd_limits))
            node_alerts = (state[:, 0] / MAX_CPU) > ALERT_CPU_THRESHOLD
            alert_flag = bool(self._forecast_alert or np.any(node_alerts))

            return {
                "state": state,
                "topology": self.topology,
                "mode": self._mode,
                "node_names": list(self.topology.names),
                "msd_limits": self.topology.msd_limits.copy(),
                "latency_matrix": self.topology.latency_matrix.copy(),
                "adj_matrix": self.topology.adj_matrix.copy(),
                "avg_cpu": avg_cpu,
                "avg_msd_usage": avg_msd_usage,
                "global_utilization": max(avg_cpu, avg_msd_usage),
                "alert_flag": alert_flag,
                "node_alerts": node_alerts.astype(bool).tolist(),
            }

    def choose_mode(self) -> HybridDecision:
        """Apply hysteresis: engage AI above 45%, release below 35%."""
        with self._lock:
            snap = self.snapshot()
            util = float(snap["global_utilization"])
            alert = bool(snap["alert_flag"])

            if alert:
                self._mode = "drl"
                reason = "forecast_alert"
            elif self._mode == "drl":
                if util < AI_RELEASE_THRESHOLD:
                    self._mode = "heuristic"
                    reason = "util_below_release_threshold"
                else:
                    reason = "hysteresis_hold_drl"
            elif util > AI_ENGAGE_THRESHOLD:
                self._mode = "drl"
                reason = "util_above_engage_threshold"
            else:
                self._mode = "heuristic"
                reason = "normal_load"

            return HybridDecision(
                mode=self._mode,
                reason=reason,
                global_utilization=util,
                avg_cpu=float(snap["avg_cpu"]),
                avg_msd_usage=float(snap["avg_msd_usage"]),
                alert_flag=alert,
            )

    def can_reserve(self, node: int, cpu_req: float, ram_req: float, msd_req: int) -> bool:
        """Check hard CPU/RAM/MSD capacity for one node."""
        cpu_used, ram_used, msd_used = self._state[node]
        msd_limit = float(self.topology.msd_limits[node])
        return (
            cpu_used + cpu_req <= MAX_CPU
            and ram_used + ram_req <= MAX_RAM
            and msd_used + msd_req <= msd_limit
        )

    def reserve_resources(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
    ) -> Tuple[bool, Optional[str]]:
        """Atomically reserve resources for the selected placement/routing pair."""
        with self._lock:
            touched = [int(v_place)]
            if int(v_route) != int(v_place):
                touched.append(int(v_route))

            for node in touched:
                if not self.can_reserve(node, cpu_req, ram_req, msd_req):
                    used = self._state[node]
                    return (
                        False,
                        (
                            f"hard_constraint_blocked node={self.topology.names[node]} "
                            f"cpu={used[0] + cpu_req:.1f}/{MAX_CPU:.1f} "
                            f"ram={used[1] + ram_req:.1f}/{MAX_RAM:.1f} "
                            f"msd={used[2] + msd_req:.1f}/{self.topology.msd_limits[node]:.1f}"
                        ),
                    )

            for node in touched:
                self._state[node, 0] += cpu_req
                self._state[node, 1] += ram_req
                self._state[node, 2] += msd_req

            return True, None

    def to_observation(self, request: Any) -> np.ndarray:
        """Build the N*6+13 observation expected by the v10 GNN policy."""
        snap = self.snapshot()
        topology = snap["topology"]
        state = snap["state"]
        node_feat_dim = 6
        req_dim = 3
        traffic_dim = 5
        global_dim = 5
        obs = np.zeros(self.num_nodes * node_feat_dim + req_dim + traffic_dim + global_dim, dtype=np.float32)
        geo_ctx = topology.get_geographic_context()
        geo_norm = geo_ctx / (float(np.max(geo_ctx)) + 1e-9)

        for node in range(self.num_nodes):
            cpu_u = state[node, 0] / MAX_CPU
            ram_u = state[node, 1] / MAX_RAM
            msd_u = state[node, 2] / topology.msd_limits[node]
            base = node * node_feat_dim
            obs[base] = cpu_u
            obs[base + 1] = ram_u
            obs[base + 2] = msd_u
            obs[base + 3] = max(0.0, 1.0 - msd_u)
            obs[base + 4] = 1.0 if (cpu_u > ALERT_CPU_THRESHOLD or snap["alert_flag"]) else 0.0
            obs[base + 5] = float(geo_norm[node])

        br = self.num_nodes * node_feat_dim
        obs[br] = float(request.cpu_req) / MAX_CPU
        obs[br + 1] = float(request.ram_req) / MAX_RAM
        obs[br + 2] = float(request.msd_req) / float(np.max(topology.msd_limits))

        svc_map = {"Video": 0, "VoIP": 1, "Data": 2, "IoT": 3, "Attack": 4}
        obs[br + req_dim + svc_map.get(request.service_type, 2)] = 1.0

        gc_base = br + req_dim + traffic_dim
        obs[gc_base] = float(snap["avg_cpu"])
        obs[gc_base + 1] = 1.0 - float(snap["avg_msd_usage"])
        obs[gc_base + 2] = obs[br]
        obs[gc_base + 3] = min(1.0, float(request.msd_req) / 6.0)
        obs[gc_base + 4] = float(request.msd_req) / float(np.max(topology.msd_limits))

        return np.clip(obs, 0.0, 1.0)

    def action_mask(self, request: Any) -> np.ndarray:
        """Mask infeasible placement and routing choices for MultiDiscrete([N, N])."""
        with self._lock:
            masks = np.ones(2 * self.num_nodes, dtype=bool)
            for node in range(self.num_nodes):
                feasible = self.can_reserve(node, request.cpu_req, request.ram_req, request.msd_req)
                masks[node] = feasible
                masks[self.num_nodes + node] = feasible
            if not masks[: self.num_nodes].any():
                masks[: self.num_nodes] = True
            if not masks[self.num_nodes :].any():
                masks[self.num_nodes :] = True
            return masks

    def as_public_dict(self) -> Dict[str, Any]:
        """Serialize state for FastAPI responses."""
        snap = self.snapshot()
        return {
            "mode": snap["mode"],
            "avg_cpu": snap["avg_cpu"],
            "avg_msd_usage": snap["avg_msd_usage"],
            "global_utilization": snap["global_utilization"],
            "alert_flag": snap["alert_flag"],
            "nodes": [
                {
                    "id": idx,
                    "name": name,
                    "cpu_used": float(snap["state"][idx, 0]),
                    "ram_used": float(snap["state"][idx, 1]),
                    "msd_used": float(snap["state"][idx, 2]),
                    "msd_limit": float(snap["msd_limits"][idx]),
                    "alert": bool(snap["node_alerts"][idx]),
                }
                for idx, name in enumerate(snap["node_names"])
            ],
        }


_STATE_MANAGER = NetworkStateManager()


def get_state_manager() -> NetworkStateManager:
    """Return the process-local singleton used by the FastAPI backend."""
    return _STATE_MANAGER
