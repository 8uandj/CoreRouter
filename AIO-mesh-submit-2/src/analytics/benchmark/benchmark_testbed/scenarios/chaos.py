from __future__ import annotations

from typing import Optional

from ..models import RequestSpec, ScenarioDefinition, RandomLike
from .common import FAR_PAIRS, request_from_profile, weighted_service


def make_request(step: int, total_steps: int, rng: RandomLike) -> Optional[RequestSpec]:
    if rng.random() > 0.95:
        return None
    alert = rng.random() < 0.15
    elephant = rng.random() < 0.25
    if rng.random() < 0.45:
        source, target = rng.choice(FAR_PAIRS)
    else:
        source = rng.randint(0, 9)
        target = rng.randint(0, 9)
        while target == source:
            target = rng.randint(0, 9)

    if alert:
        service = "Attack"
    elif elephant:
        service = "Video"
    else:
        service = weighted_service(rng)

    req = request_from_profile(
        rng,
        service,
        source=source,
        target=target,
        ttl_min=100,
        ttl_max=500,
        cpu_scale=rng.randint(3, 8) if elephant else 1.0,
        msd_extra=rng.randint(0, 4),
        alert=alert,
    )
    req.tags["chaos_alert"] = alert
    req.tags["elephant"] = elephant
    return req


scenario = ScenarioDefinition(
    name="chaos",
    title="Scenario 5 - Chaos",
    description="Saturation regime with elephants, URLLC, random alerts, and long TTL.",
    default_steps=250,
    request_factory=make_request,
)

