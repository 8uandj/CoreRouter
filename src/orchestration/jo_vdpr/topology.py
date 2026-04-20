"""
topology.py — Topology 10 Data Center Nodes (Việt Nam, Hà Nội-centric)

Dữ liệu:
    - 10 DC đặt tại các tỉnh/thành phố trải dài từ Hà Nội đến Cần Thơ.
    - Latency được tính từ khoảng cách địa lý thực (geodesic) chia cho tốc độ cáp quang.
    - MSD phản ánh thực tế phần cứng phân cấp (Core DC có Switch cao cấp hơn Edge DC).

Công thức latency:
    L(i,j) = d_km / 200_000 * 1_000_000 (μs → ms) + proc_delay_ms
    Trong đó 200,000 km/s là tốc độ ánh sáng trong cáp quang (2/3 c).
"""

import numpy as np
from math import radians, sin, cos, sqrt, atan2

# ══════════════════════════════════════════════════════════════
#  Dữ liệu địa lý: 10 Data Center Nodes
# ══════════════════════════════════════════════════════════════
DC_NODES = [
    # (Name,              Lat,     Lon,   Role,   MSD, proc_ms)
    ("Hanoi",             21.0285, 105.8542, "core",  10, 1),  # 0 — HN Core DC (Cầu Giấy)
    ("HaiPhong",          20.8449, 106.6881, "core",  10, 1),  # 1 — HP Core DC
    ("NinhBinh",          20.2541, 105.9750, "edge",   5, 2),  # 2 — NB Edge DC
    ("Vinh",              18.6796, 105.6813, "edge",   5, 2),  # 3 — Vinh (Nghệ An) Edge DC
    ("Hue",               16.4637, 107.5909, "edge",   4, 3),  # 4 — Huế Edge DC
    ("DaNang",            16.0544, 108.2022, "core",   8, 1),  # 5 — ĐN Core DC
    ("QuyNhon",           13.7830, 109.2196, "edge",   4, 3),  # 6 — Quy Nhơn Edge DC
    ("NhaTrang",          12.2388, 109.1967, "edge",   5, 2),  # 7 — Nha Trang Edge DC
    ("HoChiMinh",         10.8231, 106.6297, "core",  10, 1),  # 8 — HCM Core DC
    ("CanTho",            10.0452, 105.7469, "edge",   5, 2),  # 9 — Cần Thơ Edge DC
]

NUM_NODES = len(DC_NODES)
NAMES   = [d[0] for d in DC_NODES]
LATS    = [d[1] for d in DC_NODES]
LONS    = [d[2] for d in DC_NODES]
ROLES   = [d[3] for d in DC_NODES]
MSD_LIMITS = np.array([d[4] for d in DC_NODES], dtype=np.float32)
PROC_DELAYS = np.array([d[5] for d in DC_NODES], dtype=np.float32)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Tính khoảng cách geodesic (km) giữa 2 tọa độ lat/lon."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def build_latency_matrix() -> np.ndarray:
    """
    Trả về ma trận trễ (ms) giữa các cặp node.
    Công thức: L = d_km / 200 + avg_proc_delay (200 km/ms = tốc độ cáp quang)
    """
    L = np.zeros((NUM_NODES, NUM_NODES), dtype=np.float32)
    for i in range(NUM_NODES):
        for j in range(NUM_NODES):
            if i == j:
                continue
            d_km = _haversine_km(LATS[i], LONS[i], LATS[j], LONS[j])
            propagation_ms = d_km / 200.0         # 200 km/ms (2/3 vận tốc ánh sáng)
            proc_ms = (PROC_DELAYS[i] + PROC_DELAYS[j]) / 2.0
            L[i][j] = propagation_ms + proc_ms
    return L


# ══════════════════════════════════════════════════════════════
#  Singleton: Gọi 1 lần duy nhất, tái sử dụng trong toàn hệ thống
# ══════════════════════════════════════════════════════════════
LATENCY_MATRIX = build_latency_matrix()


def get_adjacency_matrix(threshold_ms: float = 15.0) -> np.ndarray:
    """
    Ma trận kề tĩnh (Static) dùng cho GAT base: 1 nếu latency < threshold, 0 nếu không.
    threshold_ms=15 nghĩa là các DC cách nhau < 3000km đều kết nối được.
    """
    adj = (LATENCY_MATRIX < threshold_ms).astype(np.float32)
    np.fill_diagonal(adj, 1.0)  # self-loop
    return adj


def get_dynamic_adjacency(msd_residuals: np.ndarray,
                           latency_matrix: np.ndarray = None,
                           alpha: float = 0.6,
                           beta: float = 0.4) -> np.ndarray:
    """
    Ma trận kề động (Dynamic) tích hợp MSD Residual:
        A_dynamic[i][j] = alpha * (1/latency_norm[i][j]) + beta * msd_residual_j

    Args:
        msd_residuals: (num_nodes,) — tỉ lệ MSD còn lại của từng node ∈ [0,1]
        latency_matrix: ma trận latency, mặc định dùng LATENCY_MATRIX toàn cục
        alpha: trọng số cho khoảng cách địa lý (proximity)
        beta: trọng số cho dung lượng MSD còn lại (capacity)
    """
    if latency_matrix is None:
        latency_matrix = LATENCY_MATRIX

    # Normalize latency: nghịch đảo (càng gần → weight càng cao)
    safe_lat = np.where(latency_matrix == 0, 1e-9, latency_matrix)
    inv_lat = 1.0 / safe_lat
    inv_lat_norm = inv_lat / (inv_lat.max() + 1e-9)  # → [0,1]

    # Capacity component: trọng số hàng = MSD residual của node đích j
    cap_weight = msd_residuals[np.newaxis, :]  # broadcast over rows → (N, N)

    adj_dynamic = alpha * inv_lat_norm + beta * cap_weight
    np.fill_diagonal(adj_dynamic, 1.0)  # self-loop luôn = 1
    return adj_dynamic.astype(np.float32)


# ══════════════════════════════════════════════════════════════
#  Debug / Kiểm tra
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import pandas as pd
    df = pd.DataFrame(LATENCY_MATRIX, index=NAMES, columns=NAMES)
    print("=== Latency Matrix (ms) ===")
    pd.set_option("display.float_format", "{:.1f}".format)
    print(df.to_string())
    print(f"\nMSD Limits: {dict(zip(NAMES, MSD_LIMITS.tolist()))}")
    print(f"\nLatency Range: {LATENCY_MATRIX[LATENCY_MATRIX>0].min():.2f}ms → {LATENCY_MATRIX.max():.2f}ms")
