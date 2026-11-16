"""
topology_geant2.py — GÉANT2 22-Node Topology (Pan-European Research Network)

GÉANT2 là mạng backbone pan-châu Âu giữa các trung tâm nghiên cứu:
    - 22 nodes trải dài từ Iceland đến Thổ Nhĩ Kỳ
    - Topology được sử dụng rộng rãi trong benchmark VNF Placement (2016-2024)
    - Đặc điểm: latency ngắn hơn NSFNET (châu Âu nhỏ hơn), MSD đa dạng

Tham chiếu:
    - GÉANT2 official topology: https://www.geant.org/Resources/
    - Pham & Xiong (2019), "A Comprehensive Survey on Network Function Virtualization"
      — sử dụng GÉANT2 làm benchmark chuẩn
    - Rankothge et al. (2017), "Optimizing Resource Utilization in NFV" — GÉANT benchmark
"""

import numpy as np
from math import radians, sin, cos, sqrt, atan2

from src.orchestration.jo_vdpr.topology import (
    FIBER_SPEED_KM_PER_MS,
    srv6_sid_processing_ms,
    mg1_heavy_tail_queue_delay_ms,
)


# ══════════════════════════════════════════════════════════════
#  22 GÉANT2 Nodes — Pan-European Backbone
#  (Name, Lat, Lon, Role, MSD, proc_ms)
# ══════════════════════════════════════════════════════════════
GEANT2_NODES = [
    ("Reykjavik",  64.1265, -21.8174, "edge",   4, 3),  # 0  — IS
    ("Oslo",       59.9139,  10.7522, "core",  10, 1),  # 1  — NO (Core)
    ("Stockholm",  59.3293,  18.0686, "core",  10, 1),  # 2  — SE (Core)
    ("Copenhagen", 55.6761,  12.5683, "edge",   5, 2),  # 3  — DK
    ("Amsterdam",  52.3676,   4.9041, "core",  10, 1),  # 4  — NL (AMS-IX Hub)
    ("London",     51.5074,  -0.1278, "core",  10, 1),  # 5  — UK (Core)
    ("Dublin",     53.3498,  -6.2603, "edge",   5, 2),  # 6  — IE
    ("Paris",      48.8566,   2.3522, "core",  10, 1),  # 7  — FR (Core)
    ("Brussels",   50.8503,   4.3517, "edge",   5, 2),  # 8  — BE
    ("Lisbon",     38.7223,  -9.1393, "edge",   5, 2),  # 9  — PT
    ("Madrid",     40.4168,  -3.7038, "edge",   5, 2),  # 10 — ES
    ("Bern",       46.9480,   7.4474, "core",   8, 1),  # 11 — CH (CERN-adjacent)
    ("Frankfurt",  50.1109,   8.6821, "core",  10, 1),  # 12 — DE (DE-CIX Hub)
    ("Vienna",     48.2082,  16.3738, "edge",   5, 2),  # 13 — AT
    ("Warsaw",     52.2297,  21.0122, "edge",   5, 2),  # 14 — PL
    ("Prague",     50.0755,  14.4378, "edge",   4, 2),  # 15 — CZ
    ("Budapest",   47.4979,  19.0402, "edge",   4, 2),  # 16 — HU
    ("Zagreb",     45.8150,  15.9819, "edge",   4, 3),  # 17 — HR
    ("Rome",       41.9028,  12.4964, "core",   8, 1),  # 18 — IT (Core)
    ("Athens",     37.9838,  23.7275, "edge",   5, 2),  # 19 — GR
    ("Sophia",     42.6977,  23.3219, "edge",   4, 2),  # 20 — BG
    ("Istanbul",   41.0082,  28.9784, "edge",   5, 2),  # 21 — TR
]

NUM_NODES_GEANT2   = len(GEANT2_NODES)
NAMES_GEANT2       = [d[0] for d in GEANT2_NODES]
LATS_GEANT2        = [d[1] for d in GEANT2_NODES]
LONS_GEANT2        = [d[2] for d in GEANT2_NODES]
ROLES_GEANT2       = [d[3] for d in GEANT2_NODES]
MSD_LIMITS_GEANT2  = np.array([d[4] for d in GEANT2_NODES], dtype=np.float32)
PROC_DELAYS_GEANT2 = np.array([d[5] for d in GEANT2_NODES], dtype=np.float32)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def build_geant2_latency_matrix() -> np.ndarray:
    n = NUM_NODES_GEANT2
    L = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d_km   = _haversine_km(LATS_GEANT2[i], LONS_GEANT2[i],
                                   LATS_GEANT2[j], LONS_GEANT2[j])
            D_prop = d_km / FIBER_SPEED_KM_PER_MS
            D_proc = (PROC_DELAYS_GEANT2[i] + PROC_DELAYS_GEANT2[j]) / 2.0
            L[i][j] = D_prop + D_proc
    return L


LATENCY_MATRIX_GEANT2 = build_geant2_latency_matrix()


def get_adjacency_matrix_geant2(threshold_ms: float = 10.0) -> np.ndarray:
    """Threshold 10ms (châu Âu nhỏ hơn, nhiều kết nối hơn NSFNET)."""
    adj = (LATENCY_MATRIX_GEANT2 < threshold_ms).astype(np.float32)
    np.fill_diagonal(adj, 1.0)
    return adj


def compute_request_latency_geant2(v1: int, v2: int, n_sids: int,
                                   cpu_util_v1: float = 0.5,
                                   cpu_util_v2: float = 0.5) -> dict:
    D_prop  = float(LATENCY_MATRIX_GEANT2[v1][v2])
    D_srv6  = srv6_sid_processing_ms(n_sids)
    D_queue = mg1_heavy_tail_queue_delay_ms(cpu_util_v1) + mg1_heavy_tail_queue_delay_ms(cpu_util_v2)
    D_total = D_prop + D_srv6 + D_queue
    return {"D_prop_ms": D_prop, "D_srv6_ms": D_srv6,
            "D_queue_ms": D_queue, "D_total_ms": D_total}


if __name__ == "__main__":
    import pandas as pd
    pd.set_option("display.float_format", "{:.1f}".format)
    df = pd.DataFrame(LATENCY_MATRIX_GEANT2, index=NAMES_GEANT2, columns=NAMES_GEANT2)
    print("=== GÉANT2 Latency Matrix (ms) ===")
    print(df.to_string())
    print(f"\nNodes: {NUM_NODES_GEANT2}")
    print(f"Latency Range: {LATENCY_MATRIX_GEANT2[LATENCY_MATRIX_GEANT2 > 0].min():.2f}ms → "
          f"{LATENCY_MATRIX_GEANT2.max():.2f}ms")

    print("\n=== Latency Breakdown Amsterdam → Istanbul (4 SIDs) ===")
    r = compute_request_latency_geant2(4, 21, n_sids=4, cpu_util_v1=0.7, cpu_util_v2=0.6)
    for k, v in r.items():
        print(f"  {k:<15}: {v:.4f} ms")
