"""
state_manager.py — Local State Manager for 3S-COM Orchestration (Phase 6 Alignment)
DONG BO 100% VOI TRAINING ENVIRONMENT (src/orchestration/jo_vdpr/env.py)
"""

import threading
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple

from src.orchestration.jo_vdpr.topology import DEFAULT_TOPO

# Nguong canh bao tai (Theo env.py)
ALERT_CPU_THRESHOLD = 0.80

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
    """Quan ly trang thai tai nguyen mang Local cho ca AI va Heuristic."""
    
    def __init__(self, topology=DEFAULT_TOPO):
        self.topology = topology
        self.num_nodes = topology.num_nodes
        self._lock = threading.Lock()
        self._mode = "HYBRID"
        
        # State matrix: [CPU_used, RAM_used, MSD_used]
        self._state = np.zeros((self.num_nodes, 3), dtype=np.float32)
        self._alert_active = False

    def reset(self):
        with self._lock:
            self._state.fill(0)
            self._alert_active = False

    def snapshot(self) -> NetworkSnapshot:
        """Lay anh chup trang thai mang hien tai."""
        with self._lock:
            state = self._state.copy()
            cpu_utils = state[:, 0] / MAX_CPU
            msd_utils = state[:, 2] / self.topology.msd_limits
            
            avg_cpu = float(np.mean(cpu_utils))
            avg_msd_usage = float(np.mean(msd_utils))
            
            node_list = []
            for i in range(self.num_nodes):
                node_list.append({
                    "id": i,
                    "name": self.topology.names[i],
                    "cpu_util": cpu_utils[i] * 100.0,
                    "ram_util": (state[i, 1] / MAX_RAM) * 100.0,
                    "msd_util": msd_utils[i] * 100.0,
                    "alert": bool(cpu_utils[i] > ALERT_CPU_THRESHOLD)
                })
            
            return NetworkSnapshot(
                mode=self._mode,
                avg_cpu=avg_cpu,
                avg_msd_usage=avg_msd_usage,
                global_utilization=max(avg_cpu, avg_msd_usage),
                alert_flag=bool(avg_cpu > 0.60),
                nodes=node_list,
                state=state,
                latency_matrix=self.topology.latency_matrix,
                adj_matrix=self.topology.adj_matrix,
                msd_limits=self.topology.msd_limits,
                node_names=self.topology.names
            )

    def can_reserve(self, node: int, cpu_req: float, ram_req: float, msd_req: int, other_node: Optional[int] = None) -> bool:
        """Kiem tra xem mot node co du tai nguyen khong (Hard Constraints)."""
        cpu_used = self._state[node, 0]
        ram_used = self._state[node, 1]
        msd_used = self._state[node, 2]
        msd_limit = float(self.topology.msd_limits[node])
        
        # ALIGNMENT: Revert ve logic co ban cua env.py (Khong tinh hops vao hard rejection)
        # Vi Model v10 khong duoc hoc ve chi phi Hops trong luc hoc Hard Constraints.
        actual_msd_req = msd_req

        return (
            cpu_used + cpu_req <= MAX_CPU
            and ram_used + ram_req <= MAX_RAM
            and msd_used + actual_msd_req <= msd_limit
        )

    def try_reserve(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
    ) -> Tuple[bool, Optional[str]]:
        """Thuc hien giu cho tai nguyen mot cach nguyen tu."""
        with self._lock:
            # ALIGNMENT: Khong tinh hops vao hard rejection check nhu env.py
            if not self.can_reserve(v_place, cpu_req, ram_req, msd_req):
                return False, "placement_node_full"
            
            if v_place != v_route:
                if not self.can_reserve(v_route, cpu_req, ram_req, msd_req):
                    return False, "routing_node_full"

            # Thuc hien tru tai nguyen
            # Luu y: Theo env.py, ca 2 node deu bi tru CPU/RAM/MSD neu v1 != v2
            self._state[v_place, 0] += cpu_req
            self._state[v_place, 1] += ram_req
            self._state[v_place, 2] += msd_req
            
            if v_place != v_route:
                self._state[v_route, 0] += cpu_req
                self._state[v_route, 1] += ram_req
                self._state[v_route, 2] += msd_req
            
            return True, None

    def release_resources(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
    ):
        """Hoan tra tai nguyen."""
        with self._lock:
            self._state[v_place, 0] = max(0, self._state[v_place, 0] - cpu_req)
            self._state[v_place, 1] = max(0, self._state[v_place, 1] - ram_req)
            self._state[v_place, 2] = max(0, self._state[v_place, 2] - msd_req)
            
            if v_place != v_route:
                self._state[v_route, 0] = max(0, self._state[v_route, 0] - cpu_req)
                self._state[v_route, 1] = max(0, self._state[v_route, 1] - ram_req)
                self._state[v_route, 2] = max(0, self._state[v_route, 2] - msd_req)

    def to_observation(self, request: Any) -> np.ndarray:
        """
        Chuyen doi trang thai mang sang vector Observation chuan GNN (N*6 + 13).
        DONG BO 100% VOI src/orchestration/jo_vdpr/env.py
        """
        snap = self.snapshot()
        topology = self.topology
        node_feat_dim = 6
        req_dim = 3
        svc_dim = 5
        gc_dim = 5
        
        obs_dim = (self.num_nodes * node_feat_dim + req_dim + svc_dim + gc_dim)
        obs = np.zeros(obs_dim, dtype=np.float32)

        # 1. Node Features (N * 6)
        cpu_utils = []
        msd_residuals = []
        
        # Geographic context (Duy tri ti le nhu trong env.py)
        geo_ctx = topology.lats 
        geo_norm = geo_ctx / (np.max(geo_ctx) + 1e-9)

        for node in range(self.num_nodes):
            # Scale ve [0, 1] theo dung env.py
            cpu_u = snap.state[node, 0] / 100.0 
            ram_u = snap.state[node, 1] / 100.0
            msd_u = snap.state[node, 2] / float(topology.msd_limits[node])
            msd_f = max(0.0, 1.0 - msd_u)
            
            # alert CPU > 80% (Logic Bi-GRU mo phong)
            alert = 1.0 if cpu_u > ALERT_CPU_THRESHOLD else 0.0
            
            base = node * node_feat_dim
            obs[base]     = cpu_u
            obs[base + 1] = ram_u
            obs[base + 2] = msd_u
            obs[base + 3] = msd_f
            obs[base + 4] = alert
            obs[base + 5] = float(geo_norm[node])
            
            cpu_utils.append(cpu_u)
            msd_residuals.append(msd_f)

        # 2. Request Features (3)
        br = self.num_nodes * node_feat_dim
        obs[br]     = request.cpu_req / 100.0
        obs[br + 1] = request.ram_req / 100.0
        obs[br + 2] = request.msd_req / float(topology.msd_limits.max())

        # 3. Traffic Type One-hot (5)
        svc_map = {"Video": 0, "VoIP": 1, "Data": 2, "IoT": 3, "Attack": 4}
        obs[br + req_dim + svc_map.get(request.service_type, 2)] = 1.0

        # 4. Global Context (5)
        gc_base = br + req_dim + svc_dim
        avg_cpu = float(np.mean(cpu_utils))
        avg_msd_res = float(np.mean(msd_residuals))
        
        # srv6_norm & chain_norm theo env.py
        srv6_norm = (request.msd_req * 0.05) / 0.3 
        chain_norm = request.msd_req / float(topology.msd_limits.max())

        obs[gc_base]     = avg_cpu
        obs[gc_base + 1] = avg_msd_res
        obs[gc_base + 2] = obs[br] # req_intensity
        obs[gc_base + 3] = float(np.clip(srv6_norm, 0.0, 1.0))
        obs[gc_base + 4] = float(np.clip(chain_norm, 0.0, 1.0))

        return np.clip(obs, 0.0, 1.0)

    def action_mask(self, request: Any) -> np.ndarray:
        """Tao mat na cho MaskablePPO."""
        with self._lock:
            masks = np.zeros(self.num_nodes * 2, dtype=bool)
            for node in range(self.num_nodes):
                feasible = self.can_reserve(node, request.cpu_req, request.ram_req, request.msd_req)
                masks[node] = feasible
                masks[self.num_nodes + node] = feasible
            return masks


_STATE_MANAGER = NetworkStateManager()

def get_state_manager() -> NetworkStateManager:
    return _STATE_MANAGER
