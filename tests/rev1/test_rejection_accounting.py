import unittest

from src.analytics.benchmark.benchmark_algorithm.metrics import RunMetrics


class RejectionAccountingTests(unittest.TestCase):
    def test_overlapping_candidate_violations_have_one_primary_rejection_cause(self):
        metrics = RunMetrics("baseline_protected", "chaos", "vietnam", 1)
        metrics.collect({
            "accepted": False,
            "cpu_violation": True,
            "ram_violation": True,
            "msd_violation": True,
            "bw_violation": True,
            "rejection_reason": "cpu",
        }, -1.0)
        summary = metrics.as_summary()
        self.assertEqual(summary["candidate_hard_infeasible_rate"], 100.0)
        self.assertEqual(summary["rejection_cpu_rate"], 100.0)
        self.assertEqual(summary["rejection_ram_rate"], 0.0)
        self.assertEqual(summary["rejection_msd_rate"], 0.0)
        self.assertEqual(summary["rejection_bw_rate"], 0.0)
        self.assertEqual(summary["rejection_other_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
