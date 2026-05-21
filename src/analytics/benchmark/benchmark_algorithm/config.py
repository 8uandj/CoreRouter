from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


EVAL_SEEDS = [42, 100, 2024, 8888, 9999]
RAW_SCENARIOS = {"uniform", "bursty", "heavy_tail"}
SCENARIO_CHOICES = [
    "uniform",
    "bursty",
    "heavy_tail",
    "normal_load",
    "elephant_stress",
    "burst_surge",
    "chaos",
    "thesis",
    "all",
]


@dataclass(frozen=True)
class AlgorithmBenchmarkConfig:
    topology: str = "vietnam"
    scenario: str = "uniform"
    load: str = "stress"
    version: str = "v11"
    steps: int = 3000
    single_seed: bool = False
    skip_exhaustive: bool = False
    workers: int = 1
    sla_scale: float = 1.0
    output_dir: Path = Path("results/benchmark_algorithm")
    data_path: Path = Path("data/processed/real_telecom_combined.csv")
    model_root: Path = Path("results/models")

    @property
    def seeds(self) -> List[int]:
        return [42] if self.single_seed else EVAL_SEEDS

    @property
    def arrival_rate(self) -> float:
        return 0.2 if self.load == "normal" else 1.0

    @property
    def ttl_range(self) -> Tuple[int, int]:
        return (10, 50) if self.load == "normal" else (100, 500)

    def model_path(self, topology: str) -> Path:
        return self.model_root / self.version / f"dgrl_{self.version}_final_{topology}.zip"

    def norm_path(self, topology: str) -> Path:
        return self.model_root / self.version / f"vec_normalize_{self.version}_{topology}.pkl"


def load_params(load: str) -> Tuple[float, Tuple[int, int]]:
    return (0.2, (10, 50)) if load == "normal" else (1.0, (100, 500))


def scenario_jobs(scenario: str, load: str) -> List[Tuple[str, str, str]]:
    """Return (display_scenario, env_traffic_scenario, load) jobs."""
    if scenario in RAW_SCENARIOS:
        return [(scenario, scenario, load)]
    if scenario == "normal_load":
        return [("normal_load", "uniform", "normal")]
    if scenario == "elephant_stress":
        return [("elephant_stress", "heavy_tail", "stress")]
    if scenario == "burst_surge":
        return [("burst_surge", "bursty", "stress")]
    if scenario == "chaos":
        return [("chaos", "heavy_tail", "stress")]
    if scenario == "all":
        return [(name, name, load) for name in ["uniform", "bursty", "heavy_tail"]]
    if scenario == "thesis":
        return [
            ("normal_load", "uniform", "normal"),
            ("elephant_stress", "heavy_tail", "stress"),
            ("burst_surge", "bursty", "stress"),
            ("chaos", "heavy_tail", "stress"),
        ]
    raise ValueError(f"Unsupported scenario: {scenario}")
