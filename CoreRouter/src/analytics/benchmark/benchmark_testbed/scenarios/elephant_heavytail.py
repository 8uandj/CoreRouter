from __future__ import annotations

from typing import Optional

from ..models import RequestSpec, ScenarioDefinition, RandomLike
from .common import CORE_SOURCES, EDGE_SOURCES, request_from_profile, weighted_service


def make_request(step: int, total_steps: int, rng: RandomLike) -> Optional[RequestSpec]:
    if rng.random() > 0.50:
        return None
    elephant = rng.random() < 0.20
    source = rng.choice(EDGE_SOURCES + CORE_SOURCES)
    target = rng.randint(0, 9)
    while target == source:
        target = rng.randint(0, 9)

    if elephant:
        req = request_from_profile(
            rng,
            "Video",
            source=source,
            target=target,
            ttl_min=70,
            ttl_max=180,
            cpu_scale=rng.randint(5, 10),
            msd_extra=1,
        )
        req.tags["elephant"] = True
        return req

    return request_from_profile(
        rng,
        weighted_service(rng),
        source=source,
        target=target,
        ttl_min=25,
        ttl_max=80,
    )


scenario = ScenarioDefinition(
    name="elephant_heavytail",
    title="Scenario 2 - Elephant Heavy-Tail",
    description="Pareto-like mix with 20 percent elephant flows.",
    default_steps=200,
    request_factory=make_request,
)

