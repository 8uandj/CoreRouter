"""
topology.py — Physics-Aware Latency Model v3 (Multi-Topology + Proactive Ready)
"""

import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from math import radians, sin, cos, sqrt, atan2

# ══════════════════════════════════════════════════════════════
#  Network Physical Constants
# ══════════════════════════════════════════════════════════════
SRv6_SID_PROC_MS: float = 0.05
VNF_SERVICE_TIME_MS: float = 0.1
FIBER_SPEED_KM_PER_MS: float = 200.0

TOPOLOGIES = {
    "vietnam": {
        "description": "Vietnam National Backbone (10 Nodes)",
        "p99_latency_threshold": 15.0,
        "nodes": [
            ("Hanoi",      21.0285, 105.8542, "core",  10, 1),
            ("HaiPhong",   20.8449, 106.6881, "core",  10, 1),
            ("NinhBinh",   20.2541, 105.9750, "edge",   5, 2),
            ("Vinh",       18.6796, 105.6813, "edge",   5, 2),
            ("Hue",        16.4637, 107.5909, "edge",   4, 3),
            ("DaNang",     16.0544, 108.2022, "core",   8, 1),
            ("QuyNhon",    13.7830, 109.2196, "edge",   4, 3),
            ("NhaTrang",   12.2388, 109.1967, "edge",   5, 2),
            ("HoChiMinh",  10.8231, 106.6297, "core",  10, 1),
            ("CanTho",     10.0452, 105.7469, "edge",   5, 2),
        ]
    }
}

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

class TopologyManager:
    def __init__(self, topology_name: str = "vietnam"):
        data = TOPOLOGIES[topology_name]
        self.topology_name = topology_name
        self.num_nodes = len(data["nodes"])
        self.names = [n[0] for n in data["nodes"]]
        self.lats = [n[1] for n in data["nodes"]]
        self.lons = [n[2] for n in data["nodes"]]
        self.msd_limits = np.array([n[4] for n in data["nodes"]], dtype=np.float32)
        self.proc_delays = np.array([n[5] for n in data["nodes"]], dtype=np.float32)
        self.gat_threshold = data["p99_latency_threshold"]
        
        self.latency_matrix = self._build_latency_matrix()
        self.adj_matrix = self._build_adj_matrix()
        self.hop_matrix = self._build_hop_matrix()

    def _build_latency_matrix(self) -> np.ndarray:
        L = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float32)
        for i in range(self.num_nodes):
            for j in range(self.num_nodes):
                if i == j: continue
                d_km = _haversine_km(self.lats[i], self.lons[i], self.lats[j], self.lons[j])
                L[i][j] = (d_km / FIBER_SPEED_KM_PER_MS) + (self.proc_delays[i] + self.proc_delays[j])/2
        return L

    def _build_adj_matrix(self) -> np.ndarray:
        adj = (self.latency_matrix < self.gat_threshold).astype(np.float32)
        np.fill_diagonal(adj, 1.0)
        return adj

    def _build_hop_matrix(self) -> np.ndarray:
        hops = np.full((self.num_nodes, self.num_nodes), 99, dtype=np.int32)
        np.fill_diagonal(hops, 0)
        for start in range(self.num_nodes):
            q = [(start, 0)]
            visited = {start}
            while q:
                u, d = q.pop(0)
                hops[start][u] = d
                for v in range(self.num_nodes):
                    if self.adj_matrix[u][v] > 0 and v not in visited:
                        visited.add(v)
                        q.append((v, d + 1))
        return hops

    def get_hop_distance(self, u: int, v: int) -> int:
        return int(self.hop_matrix[int(u)][int(v)])

    def get_geographic_context(self) -> np.ndarray:
        # Tính khoảng cách địa lý trung bình (theo ms) từ một node tới tất cả các node khác
        # Giúp Agent biết được vị trí tương đối (Trung tâm hay Rìa) của node
        return np.mean(self.latency_matrix, axis=1)

DEFAULT_TOPO = TopologyManager("vietnam")

def srv6_sid_processing_ms(n_sids: int) -> float:
    return float(n_sids) * SRv6_SID_PROC_MS

def mg1_heavy_tail_queue_delay_ms(cpu_util: float, lambda_rate: float = 1.0, pareto_alpha: float = 1.2) -> float:
    rho = min(0.99, max(0.01, cpu_util))
    service_time = VNF_SERVICE_TIME_MS
    variance = (service_time ** 2) * (pareto_alpha / (pareto_alpha - 1)) if pareto_alpha > 1 else service_time ** 2
    delay = (lambda_rate * variance) / (2 * (1 - rho))
    return float(delay)

def compute_request_latency(v1: int, v2: int, n_sids: int, cpu_util_v1: float, cpu_util_v2: float, latency_matrix: np.ndarray) -> dict:
    D_prop  = float(latency_matrix[v1][v2])
    D_srv6  = srv6_sid_processing_ms(n_sids)
    D_queue = mg1_heavy_tail_queue_delay_ms(cpu_util_v1) + mg1_heavy_tail_queue_delay_ms(cpu_util_v2)
    D_total = D_prop + D_srv6 + D_queue
    return {"D_prop_ms": D_prop, "D_srv6_ms": D_srv6, "D_queue_ms": D_queue, "D_total_ms": D_total}
