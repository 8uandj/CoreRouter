from __future__ import annotations

from typing import Dict, Tuple

from ..models import RequestSpec, RandomLike


SERVICE_PROFILES: Dict[str, Tuple[int, int, int]] = {
    "URLLC": (4, 2, 1),
    "VoIP": (6, 3, 1),
    "Data": (10, 5, 2),
    "Video": (18, 9, 2),
    "Attack": (55, 28, 4),
}

FAR_PAIRS = [
    (0, 9),
    (0, 8),
    (1, 9),
    (2, 8),
    (9, 0),
    (8, 0),
]

EDGE_SOURCES = [2, 4, 6, 7, 9]
CORE_SOURCES = [0, 1, 5, 8]


def weighted_service(rng: RandomLike) -> str:
    roll = rng.random()
    if roll < 0.20:
        return "URLLC"
    if roll < 0.40:
        return "VoIP"
    if roll < 0.70:
        return "Data"
    return "Video"


def request_from_profile(
    rng: RandomLike,
    service: str,
    source: int,
    target: int,
    ttl_min: int,
    ttl_max: int,
    cpu_scale: float = 1.0,
    msd_extra: int = 0,
    alert: bool = False,
) -> RequestSpec:
    cpu, ram, msd = SERVICE_PROFILES[service]
    jitter = rng.randint(0, max(1, int(cpu * 0.20)))
    cpu_req = min(100.0, (cpu + jitter) * cpu_scale)
    ram_req = min(100.0, (ram + jitter * 0.5) * cpu_scale)
    return RequestSpec(
        service_type=service,
        cpu_req=round(cpu_req, 2),
        ram_req=round(ram_req, 2),
        msd_req=max(1, min(10, msd + msd_extra)),
        source_node=source,
        destination_node=target,
        alert_flag=alert,
        is_ddos_spike=alert and service == "Attack",
        ttl_steps=rng.randint(ttl_min, ttl_max),
    )

