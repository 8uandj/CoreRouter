from __future__ import annotations

from src.orchestration.jo_vdpr.topology import DEFAULT_TOPO, compute_request_latency


def modeled_service_latency_ms(
    v_place: int,
    v_route: int,
    n_sids: int,
    cpu_util_v_place: float = 0.0,
    cpu_util_v_route: float = 0.0,
) -> float:
    result = compute_request_latency(
        v1=int(v_place),
        v2=int(v_route),
        n_sids=max(1, int(n_sids)),
        cpu_util_v1=max(0.0, min(1.0, float(cpu_util_v_place))),
        cpu_util_v2=max(0.0, min(1.0, float(cpu_util_v_route))),
        latency_matrix=DEFAULT_TOPO.latency_matrix,
    )
    return float(result["D_total_ms"])

