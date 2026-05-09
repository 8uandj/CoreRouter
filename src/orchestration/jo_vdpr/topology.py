"""
topology.py — Physics-Aware Latency Model v3 (Multi-Topology + Proactive Ready)

[NEW] Hỗ trợ cấu hình Đa mạng (Multi-Topology): 
    - 'vietnam' (10 nodes)
    - 'nsfnet'  (14 nodes)
    - 'geant2'  (22 nodes)
    Giúp chứng minh tính tổng quát (Generalization) trong luận văn.
"""

import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from math import radians, sin, cos, sqrt, atan2

# ══════════════════════════════════════════════════════════════
#  Network Physical Constants
# ══════════════════════════════════════════════════════════════
SRv6_SID_PROC_MS: float = 0.05   # ms per SID (50 μs)
VNF_SERVICE_TIME_MS: float = 0.1 # ms (100 μs)
FIBER_SPEED_KM_PER_MS: float = 200.0  # km/ms (2/3 tốc độ ánh sáng)

# ══════════════════════════════════════════════════════════════
#  TOPOLOGY DATABASE
# ══════════════════════════════════════════════════════════════

TOPOLOGIES = {
    "vietnam": {
        "description": "Vietnam National Backbone (10 Nodes)",
        "p99_latency_threshold": 15.0, # ms để thiết lập Adjacency
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
    },
    "nsfnet": {
        "description": "US NSFNET Backbone (14 Nodes)",
        "p99_latency_threshold": 30.0, # xa hơn VN, nâng threshold để GAT kết nối
        "nodes": [
            ("WA_Seattle",   47.6062, -122.3321, "edge",  6, 2),
            ("CA_PaloAlto",  37.4419, -122.1430, "core", 10, 1),
            ("CA_SanDiego",  32.7157, -117.1611, "edge",  6, 2),
            ("UT_SaltLake",  40.7608, -111.8910, "edge",  5, 2),
            ("CO_Boulder",   40.0150, -105.2705, "core",  8, 1),
            ("TX_Houston",   29.7604,  -95.3698, "core", 10, 1),
            ("NE_Lincoln",   40.8136,  -96.7026, "edge",  5, 3),
            ("IL_Champaign", 40.1164,  -88.2434, "edge",  6, 2),
            ("MI_AnnArbor",  42.2808,  -83.7430, "core",  8, 1),
            ("PA_Pittsburgh",40.4406,  -79.9959, "edge",  6, 2),
            ("NY_Ithaca",    42.4440,  -76.5019, "core", 10, 1),
            ("NJ_Princeton", 40.3573,  -74.6672, "edge",  6, 2),
            ("GA_Atlanta",   33.7490,  -84.3880, "core",  8, 1),
            ("FL_Tampa",     27.9506,  -82.4572, "edge",  5, 2),
        ]
    },
    "geant2": {
        "description": "European GEANT2 Backbone (22 Nodes)",
        "p99_latency_threshold": 25.0,
        "nodes": [
            ("UK_London",    51.5074, -0.1278,  "core", 10, 1),
            ("IE_Dublin",    53.3498, -6.2603,  "edge",  5, 2),
            ("FR_Paris",     48.8566,  2.3522,  "core", 10, 1),
            ("DE_Frankfurt", 50.1109,  8.6821,  "core", 10, 1),
            ("ES_Madrid",    40.4168, -3.7038,  "core",  8, 1),
            ("PT_Lisbon",    38.7223, -9.1393,  "edge",  4, 3),
            ("IT_Milan",     45.4642,  9.1900,  "core",  8, 1),
            ("CH_Geneva",    46.2044,  6.1432,  "core",  8, 1),
            ("AT_Vienna",    48.2082, 16.3738,  "edge",  6, 2),
            ("NL_Amsterdam", 52.3676,  4.9041,  "core", 10, 1),
            ("BE_Brussels",  50.8503,  4.3517,  "edge",  6, 2),
            ("DK_Copenhagen",55.6761, 12.5683,  "edge",  5, 2),
            ("SE_Stockholm", 59.3293, 18.0686,  "core",  8, 1),
            ("NO_Oslo",      59.9139, 10.7522,  "edge",  5, 3),
            ("FI_Helsinki",  60.1695, 24.9355,  "edge",  4, 3),
            ("PL_Poznan",    52.4064, 16.9252,  "edge",  6, 2),
            ("CZ_Prague",    50.0755, 14.4378,  "edge",  5, 2),
            ("HU_Budapest",  47.4979, 19.0402,  "edge",  5, 2),
            ("RO_Bucharest", 44.4268, 26.1025,  "edge",  4, 3),
            ("GR_Athens",    37.9838, 23.7275,  "edge",  5, 2),
            ("BG_Sofia",     42.6977, 23.3219,  "edge",  4, 3),
            ("EE_Tallinn",   59.4370, 24.7536,  "edge",  4, 3),
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
    """Quản lý các Topology riêng biệt. Hỗ trợ runtime switching."""
    
    def __init__(self, topology_name: str = "vietnam"):
        if topology_name not in TOPOLOGIES:
            raise ValueError(f"Topology {topology_name} chưa được hỗ trợ. Chọn: vietnam, nsfnet, geant2")
        
        data = TOPOLOGIES[topology_name]
        self.topology_name = topology_name
        self.description   = data["description"]
        self.gat_threshold = data["p99_latency_threshold"]
        
        nodes = data["nodes"]
        self.num_nodes   = len(nodes)
        self.names       = [n[0] for n in nodes]
        self.lats        = [n[1] for n in nodes]
        self.lons        = [n[2] for n in nodes]
        self.roles       = [n[3] for n in nodes]
        self.msd_limits  = np.array([n[4] for n in nodes], dtype=np.float32)
        self.proc_delays = np.array([n[5] for n in nodes], dtype=np.float32)
        
        self.latency_matrix = self._build_latency_matrix()
        self.adj_matrix     = self._build_adj_matrix()

    def _build_latency_matrix(self) -> np.ndarray:
        L = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float32)
        for i in range(self.num_nodes):
            for j in range(self.num_nodes):
                if i == j: continue
                d_km = _haversine_km(self.lats[i], self.lons[i], self.lats[j], self.lons[j])
                D_prop = d_km / FIBER_SPEED_KM_PER_MS
                D_proc = (self.proc_delays[i] + self.proc_delays[j]) / 2.0
                L[i][j] = D_prop + D_proc
        return L

    def _build_adj_matrix(self) -> np.ndarray:
        adj = (self.latency_matrix < self.gat_threshold).astype(np.float32)
        np.fill_diagonal(adj, 1.0)
        return adj

    def get_geographic_context(self) -> np.ndarray:
        """Trả về độ trễ trung bình từ 1 node đến tất cả các node khác."""
        return np.mean(self.latency_matrix, axis=1)

# ═══════════════════════════════════════════════════════════════
#  Thuật toán Trễ Vật lý (Không đổi so với v9, vì là chuẩn IEEE)
# ═══════════════════════════════════════════════════════════════

def srv6_sid_processing_ms(n_sids: int) -> float:
    return max(0, n_sids) * SRv6_SID_PROC_MS

def mg1_heavy_tail_queue_delay_ms(cpu_utilization: float) -> float:
    """M/G/1 Queueing with Heavy-Tail approximation (Pollaczek-Khinchine formula).
       Assumes traffic is bursty (e.g. Pareto/Weibull variance, Cv^2 ≈ 3.0)."""
    rho = float(np.clip(cpu_utilization, 0.0, 0.99))
    cv2 = 3.0 # Coefficient of Variance for bursty traffic
    return VNF_SERVICE_TIME_MS * rho * (1.0 + cv2) / (2.0 * (1.0 - rho))

def compute_request_latency(v1: int, v2: int, n_sids: int,
                            cpu_util_v1: float = 0.5, cpu_util_v2: float = 0.5,
                            latency_matrix: Optional[np.ndarray] = None) -> dict:
    
    if latency_matrix is None:
        raise ValueError("Requires latency_matrix argument in v10")
        
    D_prop  = float(latency_matrix[v1][v2])
    D_srv6  = srv6_sid_processing_ms(n_sids)
    D_q_v1  = mg1_heavy_tail_queue_delay_ms(cpu_util_v1)
    D_q_v2  = mg1_heavy_tail_queue_delay_ms(cpu_util_v2)
    D_queue = D_q_v1 + D_q_v2
    D_total = D_prop + D_srv6 + D_queue

    return {
        "D_prop_ms":   D_prop,
        "D_srv6_ms":   D_srv6,
        "D_queue_ms":  D_queue,
        "D_total_ms":  D_total,
    }

# Để backwards-compatibility với các script cũ (v9) nếu tụi nó import thẳng biến
DEFAULT_TOPO = TopologyManager("vietnam")
LATENCY_MATRIX = DEFAULT_TOPO.latency_matrix
NUM_NODES = DEFAULT_TOPO.num_nodes
MSD_LIMITS = DEFAULT_TOPO.msd_limits
NAMES = DEFAULT_TOPO.names

def get_adjacency_matrix(threshold_ms: float = 15.0) -> np.ndarray:
    return DEFAULT_TOPO.adj_matrix
