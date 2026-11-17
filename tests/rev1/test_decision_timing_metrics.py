import unittest

from src.analytics.benchmark.benchmark_algorithm.metrics import RunMetrics, aggregate_runs


class DecisionTimingMetricsTests(unittest.TestCase):
    def test_component_percentiles_and_measured_throughput_are_exported(self):
        run = RunMetrics("harp_protected", "chaos", "nsfnet", 1)
        run.acceptance.extend([True, False])
        run.decision_latency_ms.extend([10.0, 20.0])
        run.component_latencies_ms = {
            "mask_construction_ms": [1.0, 3.0],
            "admission_validation_ms": [2.0, 4.0],
        }
        run.run_wall_time_s = 2.0
        summary = run.as_summary()
        self.assertEqual(summary["decision_latency_p50_ms"], 15.0)
        self.assertEqual(summary["decision_latency_p95_ms"], 19.5)
        aggregate = aggregate_runs([run])
        self.assertEqual(aggregate["decision_latency_p99_ms"], 19.9)
        self.assertEqual(aggregate["offered_decisions_per_s"], 1.0)
        self.assertEqual(aggregate["mask_construction_ms_p95_ms"], 2.9)


if __name__ == "__main__":
    unittest.main()
