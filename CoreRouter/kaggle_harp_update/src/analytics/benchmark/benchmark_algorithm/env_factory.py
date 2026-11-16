from __future__ import annotations

from pathlib import Path
from typing import Tuple

from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import TopologyManager


def resolve_data_path(path: Path) -> Path:
    if path.exists():
        return path
    fallback = Path("data/real_telecom_combined.csv")
    return fallback if fallback.exists() else path


def make_env(
    topology_name: str,
    data_path: Path,
    steps: int,
    arrival_rate: float,
    ttl_range: Tuple[int, int],
    scenario: str,
    sla_scale: float = 1.0,
) -> JOVDPREnv:
    env = JOVDPREnv(
        repository=CSVRepository(str(resolve_data_path(data_path))),
        reward_calculator=RewardCalculator(lambda_latency=-50.0),
        topology_manager=TopologyManager(topology_name),
        episode_length=steps,
    )
    env.arrival_rate = arrival_rate
    env.ttl_range = ttl_range
    env.traffic_scenario = scenario
    if sla_scale != 1.0:
        env.LATENCY_THRESHOLDS = {
            key: max(0.1, float(value) * float(sla_scale))
            for key, value in env.LATENCY_THRESHOLDS.items()
        }
        env.reward_calc.LATENCY_THRESHOLDS = dict(env.LATENCY_THRESHOLDS)
    return env
