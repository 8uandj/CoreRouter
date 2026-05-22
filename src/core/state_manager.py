"""
state_manager.py — Local State Manager for 3S-COM Orchestration (Phase 7 Alignment)
DONG BO 100% VOI TRAINING ENVIRONMENT (src/orchestration/jo_vdpr/env.py)
TUAN THU QUY TAC KIEN TRUC 16 (HYSTERESIS GATE)
"""

import threading
import numpy as np
import time
import math
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple

from src.orchestration.jo_vdpr.topology import DEFAULT_TOPO, TopologyManager

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
    forecast_alerts: List[bool]

class NetworkStateManager:
    """
    Quan ly trang thai tai nguyen mang Local (Singleton).
    Dam bao tinh Thread-safe va tuan thu Hysteresis Gate.
    """
    
    def __init__(self, topology=DEFAULT_TOPO, topology_name: Optional[str] = None):
        self.topology = TopologyManager(topology_name) if topology_name else topology
        self.num_nodes = self.topology.num_nodes
        self._lock = threading.Lock()
        self._mode = "heuristic" # Mac dinh bat dau bang Heuristic
        
        # State matrix: [CPU_used, RAM_used, MSD_used]
        self._state = np.zeros((self.num_nodes, 3), dtype=np.float32)
        self._alert_active = False
        self._forecast_alerts = np.zeros(self.num_nodes, dtype=bool)
        
        # Registry theo doi thuc the (Ho tro Phase 7 Proactive Migration)
        self._active_vnfs: Dict[str, Dict[str, Any]] = {}
        self._pending_reservations: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        with self._lock:
            self._state.fill(0)
            self._alert_active = False
            self._forecast_alerts.fill(False)
            self._active_vnfs.clear()
            self._pending_reservations.clear()
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
                    "alert": bool(cpu_utils[i] > ALERT_CPU_THRESHOLD or self._forecast_alerts[i])
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
                node_names=self.topology.names,
                forecast_alerts=[bool(x) for x in self._forecast_alerts],
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
                self._pending_reservations[vnf_name] = {
                    "v_place": v_place, "v_route": v_route,
                    "cpu_req": cpu_req, "ram_req": ram_req, "msd_req": msd_req,
                    "timestamp": time.time()
                }
            return True, None

    def reserve_resources(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
        vnf_name: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Backwards compatibility alias for try_reserve."""
        return self.try_reserve(v_place, v_route, cpu_req, ram_req, msd_req, vnf_name)

    def release_resources(self, vnf_name: str) -> None:
        with self._lock:
            if vnf_name in self._pending_reservations:
                self._pending_reservations.pop(vnf_name)
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

    def resolve_node_id(self, vnf_name: str, location: str) -> int:
        """Map a VNF name and its location label to virtual node index 0-9."""
        name_lower = vnf_name.lower()
        loc_lower = location.lower()
        
        # Check direct location mappings
        if "hn" in loc_lower or "hanoi" in loc_lower:
            if "-hp" in name_lower: return 1
            if "-nb" in name_lower: return 2
            return 0
        if "hp" in loc_lower or "haiphong" in loc_lower:
            return 1
        if "nb" in loc_lower or "ninhbinh" in loc_lower:
            return 2
        if "vinh" in loc_lower:
            return 3
        if "hue" in loc_lower:
            return 4
        if "dn" in loc_lower or "danang" in loc_lower:
            if "-vinh" in name_lower: return 3
            if "-hue" in name_lower: return 4
            return 5
        if "qn" in loc_lower or "quynhon" in loc_lower:
            return 6
        if "nt" in loc_lower or "nhatrang" in loc_lower:
            return 7
        if "hcm" in loc_lower or "hochiminh" in loc_lower:
            if "-qn" in name_lower: return 6
            if "-nt" in name_lower: return 7
            if "-ct" in name_lower: return 9
            return 8
        if "ct" in loc_lower or "cantho" in loc_lower:
            return 9
            
        # Check fallback pattern based on names and parent cluster keys
        if "hanoi-1" in loc_lower or "k8s-master" in loc_lower:
            if "-hp" in name_lower: return 1
            if "-nb" in name_lower: return 2
            return 0
        if "danang-1" in loc_lower or "worker1" in loc_lower:
            if "-vinh" in name_lower: return 3
            if "-hue" in name_lower: return 4
            return 5
        if "hcm-1" in loc_lower or "worker2" in loc_lower:
            if "-qn" in name_lower: return 6
            if "-nt" in name_lower: return 7
            if "-ct" in name_lower: return 9
            return 8
            
        # Name-based checks
        if "-hp" in name_lower: return 1
        if "-nb" in name_lower: return 2
        if "-vinh" in name_lower: return 3
        if "-hue" in name_lower: return 4
        if "-qn" in name_lower: return 6
        if "-nt" in name_lower: return 7
        if "-ct" in name_lower: return 9
        
        # Ultimate fallback
        return 0

    def sync_with_kubernetes(self, k8s_vnfs: List[Dict[str, Any]]) -> None:
        """Synchronize in-memory VNF list and resource states with live Kubernetes deployments.
        Protects transient state by preserving pending reservations for up to 60 seconds.
        """
        with self._lock:
            # 1. Clean up expired pending reservations (older than 60 seconds)
            now = time.time()
            self._pending_reservations = {
                k: v for k, v in self._pending_reservations.items()
                if now - v["timestamp"] < 60.0
            }
            
            # 2. Check which pending reservations have appeared in k8s_vnfs
            k8s_names = {vnf["id"] for vnf in k8s_vnfs}
            for name in list(self._pending_reservations.keys()):
                if name in k8s_names:
                    self._pending_reservations.pop(name)
            
            # 3. Rebuild active VNFs registry
            new_active_vnfs = {}
            
            # First, add the actual VNFs from Kubernetes
            for vnf in k8s_vnfs:
                name = vnf["id"]
                location = vnf["data"].get("location", "auto")
                
                # Resolve node index for the VNF
                node_idx = self.resolve_node_id(name, location)
                
                # If we had it in our old active_vnfs or pending reservations, preserve its resource requirements
                if name in self._active_vnfs:
                    ref = self._active_vnfs[name]
                    cpu_req = ref.get("cpu_req", 10.0)
                    ram_req = ref.get("ram_req", 5.0)
                    msd_req = ref.get("msd_req", 2)
                    v_place = ref.get("v_place", node_idx)
                    v_route = ref.get("v_route", node_idx)
                else:
                    cpu_req = 10.0
                    ram_req = 5.0
                    msd_req = 2
                    v_place = node_idx
                    v_route = node_idx
                
                new_active_vnfs[name] = {
                    "v_place": v_place,
                    "v_route": v_route,
                    "cpu_req": cpu_req,
                    "ram_req": ram_req,
                    "msd_req": msd_req,
                    "is_pending": False
                }
            
            # Next, add any pending reservations that haven't appeared in K8s yet
            for name, ref in self._pending_reservations.items():
                new_active_vnfs[name] = {
                    "v_place": ref["v_place"],
                    "v_route": ref["v_route"],
                    "cpu_req": ref["cpu_req"],
                    "ram_req": ref["ram_req"],
                    "msd_req": ref["msd_req"],
                    "is_pending": True
                }
                
            self._active_vnfs = new_active_vnfs
            
            # 4. Rebuild self._state based on low/idle baseline + active VNFs
            t = time.time()
            for i in range(self.num_nodes):
                self._state[i, 0] = 5.0 + 3.0 * math.sin(t / 60.0 + i)
                self._state[i, 1] = 8.0 + 2.0 * math.cos(t / 60.0 + i)
                self._state[i, 2] = 0.0
                
            for name, data in self._active_vnfs.items():
                v_place = data["v_place"]
                v_route = data["v_route"]
                cpu_req = data["cpu_req"]
                ram_req = data["ram_req"]
                msd_req = data["msd_req"]
                
                # Add to placement node
                self._state[v_place, 0] += cpu_req
                self._state[v_place, 1] += ram_req
                self._state[v_place, 2] += msd_req
                
                # Add to routing node if different
                if v_place != v_route:
                    self._state[v_route, 0] += cpu_req
                    self._state[v_route, 1] += ram_req
                    self._state[v_route, 2] += msd_req
            
            # Clip state to max capacity limits
            for i in range(self.num_nodes):
                self._state[i, 0] = np.clip(self._state[i, 0], 0.0, MAX_CPU)
                self._state[i, 1] = np.clip(self._state[i, 1], 0.0, MAX_RAM)
                self._state[i, 2] = np.clip(self._state[i, 2], 0.0, float(self.topology.msd_limits[i]))

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
            "forecast_alerts": snap.forecast_alerts,
        }

    def get_vnfs_on_node(self, node_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [{"name": name, **data} for name, data in self._active_vnfs.items() 
                    if data["v_place"] == node_id or data["v_route"] == node_id]

    def set_forecast_alert(self, alert: bool) -> None:
        with self._lock:
            self._alert_active = alert
            if not alert:
                self._forecast_alerts.fill(False)

    def set_node_forecast_alert(self, node_id: int, alert: bool) -> None:
        with self._lock:
            self._forecast_alerts[int(node_id)] = bool(alert)
            self._alert_active = bool(np.any(self._forecast_alerts))

    def update_node_telemetry(
        self,
        node_id: int,
        cpu_util: Optional[float] = None,
        ram_util: Optional[float] = None,
        msd_used: Optional[float] = None,
        msd_util: Optional[float] = None,
        alert: Optional[bool] = None,
    ) -> None:
        """Ingest live telemetry as absolute node resource state.

        cpu_util/ram_util can be supplied as either 0..1 ratios or 0..100 percents.
        msd_used is absolute SID depth; msd_util is 0..1 or 0..100 utilization.
        """
        node = int(node_id)
        with self._lock:
            if cpu_util is not None:
                cpu = float(cpu_util)
                self._state[node, 0] = np.clip(cpu * 100.0 if cpu <= 1.0 else cpu, 0.0, MAX_CPU)
            if ram_util is not None:
                ram = float(ram_util)
                self._state[node, 1] = np.clip(ram * 100.0 if ram <= 1.0 else ram, 0.0, MAX_RAM)
            if msd_used is not None:
                self._state[node, 2] = np.clip(float(msd_used), 0.0, float(self.topology.msd_limits[node]))
            elif msd_util is not None:
                util = float(msd_util)
                ratio = util if util <= 1.0 else util / 100.0
                self._state[node, 2] = np.clip(
                    ratio * float(self.topology.msd_limits[node]),
                    0.0,
                    float(self.topology.msd_limits[node]),
                )
            if alert is not None:
                self._forecast_alerts[node] = bool(alert)
            self._alert_active = bool(np.any(self._forecast_alerts))

    def choose_mode(self) -> Any:
        """
        Decision Gate (Hysteresis): Quyết định chuyển đổi Heuristic <-> DRL.
        Tuan thu Quy tac 16: AI_ENGAGE=0.45, AI_RELEASE=0.35
        """
        from dataclasses import make_dataclass
        Gate = make_dataclass("Gate", [("mode", str), ("reason", str), ("global_utilization", float)])
        
        snap = self.snapshot()
        u = snap.global_utilization

        with self._lock:
            # Logic Cong Tre (Hysteresis)
            reason = "hold"
            if self._mode == "heuristic":
                if u > AI_ENGAGE_THRESHOLD or self._alert_active:
                    self._mode = "drl"
                    reason = "engage_drl_alert_or_utilization"
            else: # dang o che do drl
                if u < AI_RELEASE_THRESHOLD and not self._alert_active:
                    self._mode = "heuristic"
                    reason = "release_to_heuristic_low_utilization"
            
            return Gate(mode=self._mode, reason=reason, global_utilization=u)

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
