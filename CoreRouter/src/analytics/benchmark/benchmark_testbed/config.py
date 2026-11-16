from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BenchmarkConfig:
    api_base_url: str = "http://127.0.0.1:8000/api"
    sdn_base_url: str = "http://127.0.0.1:8765"
    output_dir: Path = Path("results/benchmark_testbed")
    steps: int = 100
    seed: int = 42
    request_timeout_s: float = 20.0
    sdn_timeout_s: float = 10.0
    poll_interval_s: float = 1.0
    migration_timeout_s: float = 90.0
    reset_before_scenario: bool = True
    cleanup_after_scenario: bool = True
    wait_for_migration: bool = True

