from __future__ import annotations

from typing import Optional

from ..models import RequestSpec, ScenarioDefinition, RandomLike
from .common import FAR_PAIRS, request_from_profile


def make_request(step: int, total_steps: int, rng: RandomLike) -> Optional[RequestSpec]:
    if rng.random() > 0.65:
        return None
    source, target = rng.choice(FAR_PAIRS)
    service = rng.choice(["Video", "Data", "Attack"])
    req = request_from_profile(
        rng,
        service,
        source=source,
        target=target,
        ttl_min=40,
        ttl_max=120,
        cpu_scale=1.5 if service != "Attack" else 1.0,
        msd_extra=rng.randint(2, 4),
    )
    req.tags["far_pair"] = True
    return req


scenario = ScenarioDefinition(
    name="topology_physics",
    title="Scenario 3 - Topology and Physics Stress",
    description="Long source-target pairs with high SRv6 SID pressure.",
    default_steps=180,
    request_factory=make_request,
)

