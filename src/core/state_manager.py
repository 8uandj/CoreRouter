"""
state_manager.py — Local State Manager for 3S-COM Orchestration (Phase 7 Alignment)
DONG BO 100% VOI TRAINING ENVIRONMENT (src/orchestration/jo_vdpr/env.py)
TUAN THU QUY TAC KIEN TRUC 16 (HYSTERESIS GATE)
"""

import threading
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple

from src.orchestration.jo_vdpr.topology import DEFAULT_TOPO

# =============================================================================
# CONSTANTS (TUAN THU .ai/ARCHITECTURE.MD)
# =============================================================================
ALERT_CPU_THRESHOLD = 0.80
AI_ENGAGE_THRESHOLD = 0.45
AI_RELEASE_THRESHOLD = 0.35
MAX_CPU = 100.0
MAX_RAM = 100.0

@dataclass
class NetworkSnapshot:
    mode: str
    avg_cpu: float
    avg_msd_usage: float
    global_utilization: float
    alert_flag: bool
    nodes: List[Dict[str, Any]]
    state: np.ndarray 
    latency_matrix: np.ndarray
    adj_matrix: np.ndarray
    msd_limits: np.ndarray
    node_names: List[str]

class NetworkStateManager:
    """
    Quan ly trang thai tai nguyen mang Local (Singleton).
    Dam bao tinh Thread-safe va tuan thu Hysteresis Gate.
    """
    
    def __init__(self, topology=DEFAULT_TOPO):
        self.topology = topology
        self.num_nodes = topology.num_nodes
        self._lock = threading.Lock()
        self._mode = "heuristic" # Mac dinh bat dau bang Heuristic
        
        # State matrix: [CPU_used, RAM_used, MSD_used]
        self._state = np.zeros((self.num_nodes, 3), dtype=np.float32)
        self._alert_active = False
        
        # Registry theo doi thuc the (Ho tro Phase 7 Proactive Migration)
        self._active_vnfs: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        with self._lock:
            self._state.fill(0)
            self._alert_active = False
            self._active_vnfs.clear()
            self._mode = "heuristic"

    def snapshot(self) -> NetworkSnapshot:
        with self._lock:
            state = self._state.copy()
            cpu_utils = state[:, 0] / MAX_CPU
            msd_utils = state[:, 2] / self.topology.msd_limits
            
            avg_cpu = float(np.mean(cpu_utils))
            avg_msd_usage = float(np.mean(msd_utils))
            global_util = max(avg_cpu, avg_msd_usage)
            
            node_list = []
            for i in range(self.num_nodes):
                node_list.append({
                    "id": i,
                    "name": self.topology.names[i],
                    "cpu_util": float(cpu_utils[i] * 100.0),
                    "ram_util": float((state[i, 1] / MAX_RAM) * 100.0),
                    "msd_util": float(msd_utils[i] * 100.0),
                    "alert": bool(cpu_utils[i] > ALERT_CPU_THRESHOLD)
                })
            
            return NetworkSnapshot(
                mode=self._mode,
                avg_cpu=avg_cpu,
                avg_msd_usage=avg_msd_usage,
                global_utilization=global_util,
                alert_flag=self._alert_active,
                nodes=node_list,
                state=state,
                latency_matrix=self.topology.latency_matrix,
                adj_matrix=self.topology.adj_matrix,
                msd_limits=self.topology.msd_limits,
                node_names=self.topology.names
            )

    def can_reserve(self, node: int, cpu_req: float, ram_req: float, msd_req: int) -> bool:
        cpu_used = self._state[node, 0]
        ram_used = self._state[node, 1]
        msd_used = self._state[node, 2]
        msd_limit = float(self.topology.msd_limits[node])
        
        return (
            cpu_used + cpu_req <= MAX_CPU
            and ram_used + ram_req <= MAX_RAM
            and msd_used + msd_req <= msd_limit
        )

    def try_reserve(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
        vnf_name: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        with self._lock:
            if not self.can_reserve(v_place, cpu_req, ram_req, msd_req):
                return False, "placement_node_full"
            
            if v_place != v_route:
                if not self.can_reserve(v_route, cpu_req, ram_req, msd_req):
                    return False, "routing_node_full"

            self._state[v_place, 0] += cpu_req
            self._state[v_place, 1] += ram_req
            self._state[v_place, 2] += msd_req
            
            if v_place != v_route:
                self._state[v_route, 0] += cpu_req
                self._state[v_route, 1] += ram_req
                self._state[v_route, 2] += msd_req
            
            if vnf_name:
                self._active_vnfs[vnf_name] = {
                    "v_place": v_place, "v_route": v_route,
                    "cpu_req": cpu_req, "ram_req": ram_req, "msd_req": msd_req
                }
            return True, None

    def release_resources(self, vnf_name: str) -> None:
        with self._lock:
            if vnf_name not in self._active_vnfs:
                return
            data = self._active_vnfs.pop(vnf_name)
            for node_key in ["v_place", "v_route"]:
                node_id = data[node_key]
                self._state[node_id, 0] = max(0, self._state[node_id, 0] - data["cpu_req"])
                self._state[node_id, 1] = max(0, self._state[node_id, 1] - data["ram_req"])
                self._state[node_id, 2] = max(0, self._state[node_id, 2] - data["msd_req"])
                if data["v_place"] == data["v_route"]: break # Neu trung node thi thoat som

    def free_resources(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
    ) -> None:
        """Release resources for TTL-based SFC expiry without a tracked VNF name."""
        with self._lock:
            for node_id in {int(v_place), int(v_route)}:
                self._state[node_id, 0] = max(0, self._state[node_id, 0] - cpu_req)
                self._state[node_id, 1] = max(0, self._state[node_id, 1] - ram_req)
                self._state[node_id, 2] = max(0, self._state[node_id, 2] - msd_req)

    def as_public_dict(self) -> Dict[str, Any]:
        """Return the UI/API-safe snapshot shape used by orchestration routes."""
        snap = self.snapshot()
        return {
            "mode": snap.mode,
            "avg_cpu": snap.avg_cpu,
            "avg_msd_usage": snap.avg_msd_usage,
            "global_utilization": snap.global_utilization,
            "alert_flag": snap.alert_flag,
            "nodes": snap.nodes,
            "active_vnfs": [
                {"name": name, **data}
                for name, data in self._active_vnfs.items()
            ],
        }

    def get_vnfs_on_node(self, node_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [{"name": name, **data} for name, data in self._active_vnfs.items() 
                    if data["v_place"] == node_id or data["v_route"] == node_id]

    def set_forecast_alert(self, alert: bool) -> None:
        with self._lock:
            self._alert_active = alert

    def choose_mode(self) -> Any:
        """
        Decision Gate (Hysteresis): Quyết định chuyển đổi Heuristic <-> DRL.
        Tuan thu Quy tac 16: AI_ENGAGE=0.45, AI_RELEASE=0.35
        """
        from dataclasses import make_dataclass
        Gate = make_dataclass("Gate", [("mode", str)])
        
        snap = self.snapshot()
        u = snap.global_utilization

        with self._lock:
            # Logic Cong Tre (Hysteresis)
            if self._mode == "heuristic":
                if u > AI_ENGAGE_THRESHOLD or self._alert_active:
                    self._mode = "drl"
            else: # dang o che do drl
                if u < AI_RELEASE_THRESHOLD and not self._alert_active:
                    self._mode = "heuristic"
            
            return Gate(mode=self._mode)

    def action_mask(self, request: Any) -> np.ndarray:
        with self._lock:
            masks = np.zeros(self.num_nodes * 2, dtype=bool)
            for node in range(self.num_nodes):
                feasible = self.can_reserve(node, request.cpu_req, request.ram_req, request.msd_req)
                masks[node] = feasible
                masks[self.num_nodes + node] = feasible
            return masks

    def to_observation(self, request: Any) -> np.ndarray:
        """
        Chuyen doi sang vector Observation chuan GNN (N*6 + 13).
        DONG BO 100% VOI src/orchestration/jo_vdpr/env.py
        """
        snap = self.snapshot()
        topology = self.topology
        node_feat_dim, req_dim, svc_dim, gc_dim = 6, 3, 5, 5
        
        obs = np.zeros((self.num_nodes * node_feat_dim + req_dim + svc_dim + gc_dim), dtype=np.float32)
        geo_norm = topology.lats / (np.max(topology.lats) + 1e-9)

        for node in range(self.num_nodes):
            cpu_u = snap.state[node, 0] / 100.0 
            ram_u = snap.state[node, 1] / 100.0
            msd_u = snap.state[node, 2] / float(topology.msd_limits[node])
            msd_f = max(0.0, 1.0 - msd_u)
            alert = 1.0 if cpu_u > ALERT_CPU_THRESHOLD else 0.0
            base = node * node_feat_dim
            obs[base:base+6] = [cpu_u, ram_u, msd_u, msd_f, alert, float(geo_norm[node])]
            
        br = self.num_nodes * node_feat_dim
        obs[br:br+3] = [request.cpu_req/100.0, request.ram_req/100.0, request.msd_req/float(topology.msd_limits.max())]
        
        svc_map = {"Video": 0, "VoIP": 1, "Data": 2, "IoT": 3, "Attack": 4}
        obs[br+3+svc_map.get(request.service_type, 2)] = 1.0
        
        gc_base = br + req_dim + svc_dim
        obs[gc_base:gc_base+5] = [
            snap.avg_cpu, 
            snap.avg_msd_usage, 
            obs[br], # req_intensity
            (request.msd_req * 0.05) / 0.3, # srv6_norm
            request.msd_req / float(topology.msd_limits.max()) # chain_norm
        ]
        return np.clip(obs, 0.0, 1.0)

_STATE_MANAGER = NetworkStateManager()

def get_state_manager() -> NetworkStateManager:
    return _STATE_MANAGER
