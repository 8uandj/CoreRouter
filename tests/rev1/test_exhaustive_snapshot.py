import unittest

from src.analytics.benchmark.benchmark_algorithm.algorithms import _restore_env, _snapshot_env, run_exhaustive
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env
from src.analytics.benchmark.benchmark_algorithm.config import load_params
from src.analytics.benchmark.benchmark_algorithm.env_factory import resolve_data_path
from pathlib import Path


class ExhaustiveSnapshotTests(unittest.TestCase):
    def test_exhaustive_benchmark_collects_one_step(self):
        data = resolve_data_path(Path("data/real_telecom_combined.csv"))
        arrival, ttl = load_params("stress")

        def make_env_fn():
            return make_env("vietnam", data, 1, arrival, ttl, "uniform")

        metrics = run_exhaustive(make_env_fn, "uniform", steps=1, seed=42)
        self.assertEqual(metrics.requests, 1)

    def test_counterfactual_candidate_rolls_back_lifecycle_and_workload_state(self):
        data = resolve_data_path(Path("data/real_telecom_combined.csv"))
        arrival, ttl = load_params("stress")
        env = make_env("vietnam", data, 4, arrival, ttl, "chaos")
        try:
            env.reset(seed=123)
            env.step(0)
            before = _snapshot_env(env)
            env.step(1)
            _restore_env(env, before)
            after = _snapshot_env(env)
            self.assertEqual(before["step"], after["step"])
            self.assertEqual(before["request"], after["request"])
            self.assertEqual(before["active"], after["active"])
            self.assertEqual(before["lifecycle_rng"], after["lifecycle_rng"])
            self.assertEqual(before["traffic_rng"], after["traffic_rng"])
            self.assertTrue((before["state"] == after["state"]).all())
            self.assertTrue((before["bandwidth"] == after["bandwidth"]).all())
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
