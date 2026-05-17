from __future__ import annotations

from typing import Optional

from ..models import RequestSpec, ScenarioDefinition, RandomLike
from .common import request_from_profile, weighted_service


def make_request(step: int, total_steps: int, rng: RandomLike) -> Optional[RequestSpec]:
    if rng.random() > 0.20:
        return None
    source = rng.randint(0, 9)
    target = rng.randint(0, 9)
    while target == source:
        target = rng.randint(0, 9)
    return request_from_profile(
        rng,
        weighted_service(rng),
        source=source,
        target=target,
        ttl_min=10,
        ttl_max=50,
    )


scenario = ScenarioDefinition(
    name="normal_load",
    title="Scenario 1 - Normal Load",
    description="Low arrival rate, short VNF TTL, uniform traffic.",
    default_steps=200,
    request_factory=make_request,
)

