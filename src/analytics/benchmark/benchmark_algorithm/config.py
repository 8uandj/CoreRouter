from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


EVAL_SEEDS = [42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718]
REAL_TOPOLOGIES = ("vietnam", "nsfnet", "geant2")
SCALABILITY_TOPOLOGIES = ("synthetic_25", "synthetic_50", "synthetic_100")
SIZE_SWEEP_TOPOLOGIES = ("vietnam",) + SCALABILITY_TOPOLOGIES
TOPOLOGY_CHOICES = REAL_TOPOLOGIES + SCALABILITY_TOPOLOGIES + ("all", "scalability")
RAW_SCENARIOS = {"uniform", "bursty", "heavy_tail", "chaos"}
SCENARIO_CHOICES = [
    "uniform",
    "bursty",
    "heavy_tail",
    "normal_load",
    "elephant_stress",
    "burst_surge",
    "chaos",
    "thesis",
    "ablation",
    "all",
]


def topologies_for_selection(selection: str) -> List[str]:
    if selection == "all":
        return list(REAL_TOPOLOGIES)
    if selection == "scalability":
        return list(SIZE_SWEEP_TOPOLOGIES)
    if selection in TOPOLOGY_CHOICES:
        return [selection]
    raise ValueError(f"Unsupported topology selection: {selection}")


@dataclass(frozen=True)
class AlgorithmBenchmarkConfig:
    topology: str = "vietnam"
    scenario: str = "uniform"
    load: str = "stress"
    version: str = "v11"
    steps: int = 3000
    single_seed: bool = False
    seed_override: Tuple[int, ...] | None = None
    skip_exhaustive: bool = False
    workers: int = 1
    sla_scale: float = 1.0
    output_dir: Path = Path("results/benchmark_algorithm")
    data_path: Path = Path("data/processed/real_telecom_combined.csv")
    model_root: Path = Path("results/models")
    model_override: Path | None = None
    normalizer_override: Path | None = None

    def __post_init__(self):
        if self.seed_override is not None:
            if self.single_seed or not self.seed_override or len(set(self.seed_override)) != len(self.seed_override):
                raise ValueError("explicit seeds must be unique, nonempty and cannot accompany single_seed")

    @property
    def seeds(self) -> List[int]:
        return list(self.seed_override) if self.seed_override is not None else ([42] if self.single_seed else list(EVAL_SEEDS))

    @property
    def arrival_rate(self) -> float:
        return 0.2 if self.load == "normal" else 1.0

    @property
    def ttl_range(self) -> Tuple[int, int]:
        return (10, 50) if self.load == "normal" else (100, 500)

    def model_path(self, topology: str) -> Path:
        """Resolve the main policy checkpoint; ablation artifacts are never implicit here."""
        if self.model_override is not None:
            return self.model_override
        candidates = [
            self.model_root / self.version / f"dgrl_{self.version}_final_{topology}.zip",
            self.model_root / self.version / f"dgrl_{self.version}_{topology}.zip",
        ]
        return next((path for path in candidates if path.exists()), candidates[0])

    def norm_path(self, topology: str) -> Path:
        """Return the main policy's normalizer, paired by topology and version."""
        if self.normalizer_override is not None:
            return self.normalizer_override
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
        return [("chaos", "chaos", "stress")]
    if scenario == "all":
        return [(name, name, load) for name in ["uniform", "bursty", "heavy_tail", "chaos"]]
    if scenario == "thesis":
        return [
            ("normal_load", "uniform", "normal"),
            ("elephant_stress", "heavy_tail", "stress"),
            ("burst_surge", "bursty", "stress"),
            ("chaos", "chaos", "stress"),
        ]
    if scenario == "ablation":
        return [
            ("elephant_stress", "heavy_tail", "stress"),
            ("burst_surge", "bursty", "stress"),
            ("chaos", "chaos", "stress"),
        ]
    raise ValueError(f"Unsupported scenario: {scenario}")
