"""
topology_nsfnet.py — NSFNET 14-Node Topology (USA National Science Foundation Network)

Topology chuẩn học thuật được dùng trong hàng trăm paper NFV/SFC:
    - 14 nodes trải dài từ Seattle (Tây) đến Atlanta (Đông)
    - Latency geodesic thực (Haversine + fiber speed 200,000 km/s)
    - MSD limits phân cấp: Core node (NYU/UIUC/Stanford) > Regional > Edge

Tham chiếu:
    - Huitema & Srinivasan (1994), "NSFNET: A Partnership for High-Speed Networking"
    - Bhamare et al. (2016), "A Survey on Service Function Chaining" — sử dụng NSFNET
    - Luizelli et al. (2015), "Piecing Together the NFV Provisioning Puzzle" — NSFNET benchmark

Dùng để validate KHẢ NĂNG TỔNG QUÁT HÓA của JO-VPPM:
    Train trên Vietnam backbone (10 nodes) → Test trên NSFNET (14 nodes)
    Nếu acceptance ratio vẫn tốt → model không overfit topology.
"""

import numpy as np
from math import radians, sin, cos, sqrt, atan2

from src.orchestration.jo_vdpr.topology import (
    SRv6_SID_PROC_MS,
    VNF_SERVICE_TIME_MS,
    FIBER_SPEED_KM_PER_MS,
    srv6_sid_processing_ms,
    mg1_heavy_tail_queue_delay_ms,
)


# ══════════════════════════════════════════════════════════════
#  14 NSFNET Nodes (US Backbone 1991 layout)
#  (Name, Lat, Lon, Role, MSD, proc_ms)
# ══════════════════════════════════════════════════════════════
NSFNET_NODES = [
    ("Seattle",      47.6062, -122.3321, "core",   10, 1),  # 0  — Pacific NW Hub
    ("PaloAlto",     37.4419, -122.1430, "core",   10, 1),  # 1  — Stanford Research
    ("SanDiego",     32.7157,  -117.1611,"edge",    5, 2),  # 2  — SDSC
    ("SaltLakeCity", 40.7608,  -111.8910,"edge",    5, 2),  # 3  — Utah Supercomputer
    ("Boulder",      40.0150,  -105.2705,"edge",    4, 2),  # 4  — NCAR
    ("Houston",      29.7604,   -95.3698,"edge",    5, 2),  # 5  — Rice University
    ("Lincoln",      40.8136,   -96.7026,"edge",    4, 3),  # 6  — UNL
    ("Champaign",    40.1164,   -88.2434,"core",    8, 1),  # 7  — UIUC (NCSA)
    ("Pittsburgh",   40.4406,   -79.9959,"core",    8, 1),  # 8  — CMU/Pitt
    ("Atlanta",      33.7490,   -84.3880,"core",   10, 1),  # 9  — Georgia Tech
    ("AnnArbor",     42.2808,   -83.7430,"edge",    5, 2),  # 10 — UMich
    ("Princeton",    40.3573,   -74.6672,"core",   10, 1),  # 11 — Princeton / NY
    ("Ithaca",       42.4440,   -76.5019,"edge",    4, 3),  # 12 — Cornell
    ("Washington",   38.9072,   -77.0369,"core",    8, 1),  # 13 — NSF HQ / GMU
]

NUM_NODES_NSFNET   = len(NSFNET_NODES)
NAMES_NSFNET       = [d[0] for d in NSFNET_NODES]
LATS_NSFNET        = [d[1] for d in NSFNET_NODES]
LONS_NSFNET        = [d[2] for d in NSFNET_NODES]
ROLES_NSFNET       = [d[3] for d in NSFNET_NODES]
MSD_LIMITS_NSFNET  = np.array([d[4] for d in NSFNET_NODES], dtype=np.float32)
PROC_DELAYS_NSFNET = np.array([d[5] for d in NSFNET_NODES], dtype=np.float32)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def build_nsfnet_latency_matrix() -> np.ndarray:
    """Propagation + hardware processing latency matrix (ms)."""
    n = NUM_NODES_NSFNET
    L = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d_km   = _haversine_km(LATS_NSFNET[i], LONS_NSFNET[i],
                                   LATS_NSFNET[j], LONS_NSFNET[j])
            D_prop = d_km / FIBER_SPEED_KM_PER_MS
            D_proc = (PROC_DELAYS_NSFNET[i] + PROC_DELAYS_NSFNET[j]) / 2.0
            L[i][j] = D_prop + D_proc
    return L


LATENCY_MATRIX_NSFNET = build_nsfnet_latency_matrix()


def get_adjacency_matrix_nsfnet(threshold_ms: float = 20.0) -> np.ndarray:
    """Static adjacency for NSFNET (larger threshold due to US continental scale)."""
    adj = (LATENCY_MATRIX_NSFNET < threshold_ms).astype(np.float32)
    np.fill_diagonal(adj, 1.0)
    return adj


def compute_request_latency_nsfnet(v1: int, v2: int, n_sids: int,
                                   cpu_util_v1: float = 0.5,
                                   cpu_util_v2: float = 0.5) -> dict:
    """4-component latency model cho NSFNET topology."""
    D_prop  = float(LATENCY_MATRIX_NSFNET[v1][v2])
    D_srv6  = srv6_sid_processing_ms(n_sids)
    D_queue = mg1_heavy_tail_queue_delay_ms(cpu_util_v1) + mg1_heavy_tail_queue_delay_ms(cpu_util_v2)
    D_total = D_prop + D_srv6 + D_queue
    return {
        "D_prop_ms":  D_prop,
        "D_srv6_ms":  D_srv6,
        "D_queue_ms": D_queue,
        "D_total_ms": D_total,
    }


if __name__ == "__main__":
    import pandas as pd
    pd.set_option("display.float_format", "{:.1f}".format)
    df = pd.DataFrame(LATENCY_MATRIX_NSFNET, index=NAMES_NSFNET, columns=NAMES_NSFNET)
    print("=== NSFNET Latency Matrix (ms) ===")
    print(df.to_string())
    print(f"\nLatency Range: {LATENCY_MATRIX_NSFNET[LATENCY_MATRIX_NSFNET > 0].min():.2f}ms → "
          f"{LATENCY_MATRIX_NSFNET.max():.2f}ms")
    print(f"MSD Limits: {dict(zip(NAMES_NSFNET, MSD_LIMITS_NSFNET.tolist()))}")

    print("\n=== Latency Breakdown Seattle → Atlanta (3 SIDs) ===")
    r = compute_request_latency_nsfnet(0, 9, n_sids=3, cpu_util_v1=0.6, cpu_util_v2=0.5)
    for k, v in r.items():
        print(f"  {k:<15}: {v:.4f} ms")
