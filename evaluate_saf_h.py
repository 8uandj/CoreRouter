import sys
from pathlib import Path
import numpy as np

from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env
from src.analytics.benchmark.benchmark_algorithm.algorithms import run_saf_h
from src.analytics.benchmark.benchmark_algorithm.metrics import aggregate_runs

seeds = [42, 100, 2024, 8888, 9999]
# The ablation scenarios are elephant_stress (heavy_tail), burst_surge (bursty), chaos (heavy_tail/chaos)
# Let's map them to the env scenarios:
scenarios = [
    ("elephant", "heavy_tail"),
    ("burst surge", "bursty"),
    ("chaos", "heavy_tail")  # Actually chaos uses 'heavy_tail' but in run_all it might have a different logic? No, it just sets scenario to heavy_tail. Wait, what makes 'chaos' chaos in env?
]
topologies = ["vietnam", "nsfnet", "geant2"]
steps = 3000
data_path = Path("data/real_telecom_combined.csv")

for topo in topologies:
    for sc_name, env_sc in scenarios:
        runs = []
        for seed in seeds:
            def make_env_fn():
                # In ablation/chaos, env_sc is heavy_tail.
                env = make_env(
                    topology_name=topo,
                    data_path=data_path,
                    steps=steps,
                    arrival_rate=1.0,
                    ttl_range=(100, 500),
                    scenario=env_sc,
                    sla_scale=1.0,
                )
                return env
            
            metrics = run_saf_h(make_env_fn, env_sc, steps, seed)
            runs.append(metrics)
        
        agg = aggregate_runs(runs)
        print(f"Topology: {topo}, Scenario: {sc_name}")
        print(f"  Acc Rate: {agg['acceptance_rate_mean']:.1f}%")
        print(f"  MSD Viol: {agg.get('msd_violation_rate_mean', 0.0):.1f}%")
        print(f"  Lat (ms): {agg['avg_latency_ms_mean']:.1f}")

