import unittest

from src.analytics.benchmark.benchmark_algorithm.metrics import RunMetrics
from src.analytics.benchmark.benchmark_algorithm.run_all import (
    expected_benchmark_algorithms,
    validate_benchmark_coverage,
)


def metric(algorithm, trace="same", requests=2):
    result = RunMetrics(algorithm, "chaos", "vietnam", 42)
    for step in range(2):
        result.collect({"trace_request": {"step": step, "trace": trace}, "accepted": True,
                        "total_latency_ms": 1.0, "latency_threshold_ms": 10.0}, 1.0)
    if requests == 0:
        result.acceptance.clear()
    # Trace digest comes from records, so align fixture payload for both policies.
    return result


class BenchmarkCoverageTests(unittest.TestCase):
    def test_expected_algorithm_matrix_includes_both_exhaustive_modes(self):
        expected = expected_benchmark_algorithms(include_exhaustive=True)
        self.assertIn("exhaustive_pair_search_protected", expected)
        self.assertIn("exhaustive_pair_search_unprotected", expected)
        self.assertEqual(len(expected), 10)

    def test_complete_matched_seed_and_policy_matrix_passes(self):
        runs = [(42, {name: metric(name) for name in ("harp", "saf_h")})]
        validate_benchmark_coverage(runs, [42], 2, ["harp", "saf_h"])

    def test_missing_policy_seed_trace_or_empty_offers_fail(self):
        with self.assertRaisesRegex(RuntimeError, "coverage mismatch"):
            validate_benchmark_coverage([(42, {"harp": metric("harp")})], [42, 7], 2, ["harp"])
        with self.assertRaisesRegex(RuntimeError, "policy coverage"):
            validate_benchmark_coverage([(42, {"harp": metric("harp")})], [42], 2, ["harp", "saf_h"])
        empty = metric("harp", requests=0)
        with self.assertRaisesRegex(RuntimeError, "No offered requests"):
            validate_benchmark_coverage([(42, {"harp": empty})], [42], 2, ["harp"])
        mismatched = {"harp": metric("harp"), "saf_h": metric("saf_h", trace="different")}
        with self.assertRaisesRegex(RuntimeError, "different offered traces"):
            validate_benchmark_coverage([(42, mismatched)], [42], 2, ["harp", "saf_h"])

    def test_missing_trace_records_fail_even_when_policies_match(self):
        harp = RunMetrics("harp", "chaos", "vietnam", 42)
        saf_h = RunMetrics("saf_h", "chaos", "vietnam", 42)
        for run in (harp, saf_h):
            run.collect({"accepted": True}, 1.0)
        with self.assertRaisesRegex(RuntimeError, "Trace length mismatch"):
            validate_benchmark_coverage(
                [(42, {"harp": harp, "saf_h": saf_h})], [42], 2, ["harp", "saf_h"]
            )


if __name__ == "__main__":
    unittest.main()
