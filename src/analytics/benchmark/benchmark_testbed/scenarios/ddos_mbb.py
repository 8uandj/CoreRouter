from __future__ import annotations

from typing import Optional

from ..models import RequestSpec, ScenarioDefinition, RandomLike
from .common import request_from_profile, weighted_service


def make_request(step: int, total_steps: int, rng: RandomLike) -> Optional[RequestSpec]:
    surge_start = max(1, total_steps // 3)
    if step < surge_start:
        if rng.random() > 0.35:
            return None
        target = rng.randint(1, 9)
        return request_from_profile(
            rng,
            weighted_service(rng),
            source=0,
            target=target,
            ttl_min=60,
            ttl_max=140,
        )

    if rng.random() > 0.85:
        return None
    target = rng.choice([1, 3, 5, 8])
    req = request_from_profile(
        rng,
        "Attack",
        source=0,
        target=target,
        ttl_min=80,
        ttl_max=220,
        cpu_scale=1.0,
        msd_extra=rng.randint(0, 2),
        alert=True,
    )
    req.tags["ddos_surge"] = True
    return req


scenario = ScenarioDefinition(
    name="ddos_mbb",
    title="Scenario 4 - DDoS and Make-Before-Break",
    description="Alert-driven surge from Hanoi to exercise proactive migration.",
    default_steps=160,
    request_factory=make_request,
)

