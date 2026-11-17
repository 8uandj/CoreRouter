import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.analytics.ablation_study import (
    AblationMetrics, Variant, VARIANTS, resolve_variant_model_paths, validate_coverage,
)


class AblationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.variant = Variant("v", "V", "test")

    def record(self, seed, steps=2, skipped=1, key="v"):
        trace_records = [{"step": step, "cpu": 1.0} for step in range(steps + skipped)]
        return AblationMetrics(key, key, "test", "vietnam", "chaos", seed,
                               "fixture", steps=steps, skipped=skipped,
                               trace_records=trace_records)

    def test_exact_variant_seed_and_step_coverage_passes(self):
        validate_coverage([self.record(1), self.record(2)], [self.variant], [1, 2], 3)

    def test_missing_duplicate_and_incomplete_runs_fail(self):
        with self.assertRaisesRegex(RuntimeError, "coverage mismatch"):
            validate_coverage([self.record(1)], [self.variant], [1, 2], 3)
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            validate_coverage([self.record(1), self.record(1)], [self.variant], [1], 3)
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            validate_coverage([self.record(1, steps=1, skipped=1)], [self.variant], [1], 3)

    def test_soft_msd_admission_pair_reuses_soft_policy_but_changes_admission(self):
        off = next(v for v in VARIANTS if v.key == "harp_soft_msd_penalty")
        on = next(v for v in VARIANTS if v.key == "harp_soft_msd_admission")
        self.assertFalse(off.enforce_msd_constraint)
        self.assertTrue(on.enforce_msd_constraint)
        self.assertEqual(on.model_key, off.key)
        self.assertTrue(on.soft_msd_penalty)
        self.assertFalse(on.use_hard_mask)

    def test_evaluation_only_soft_msd_admission_resolves_trained_checkpoint_alias(self):
        variant = next(v for v in VARIANTS if v.key == "harp_soft_msd_admission")
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "ablation" / "harp_soft_msd_penalty"
            root.mkdir(parents=True)
            model = root / "dgrl_v11_harp_soft_msd_penalty_vietnam.zip"
            norm = root / "vec_normalize_v11_harp_soft_msd_penalty_vietnam.pkl"
            model.touch()
            norm.touch()
            resolved_model, resolved_norm, source = resolve_variant_model_paths(
                Path(tmp), "v11", "vietnam", variant
            )
        self.assertEqual(resolved_model, model)
        self.assertEqual(resolved_norm, norm)
        self.assertIn("reused for harp_soft_msd_admission", source)

    def test_coverage_rejects_variant_trace_mismatch(self):
        variants = [Variant("a", "A", "test"), Variant("b", "B", "test")]
        first = self.record(1, steps=2, skipped=1, key="a")
        second = self.record(1, steps=2, skipped=1, key="b")
        second.trace_records[1]["cpu"] = 2.0
        with self.assertRaisesRegex(RuntimeError, "different workload traces"):
            validate_coverage([first, second], variants, [1], 3)

    def test_ablation_accounting_keeps_overlapping_proposed_reasons_and_safe_rate(self):
        metrics = AblationMetrics("x", "X", "test", "vietnam", "chaos", 1, "fixture")
        metrics.collect({
            "accepted": True,
            "cpu_violation": True,
            "ram_violation": False,
            "bw_violation": False,
            "msd_violation": True,
            "admitted_cpu_violation": True,
            "admitted_ram_violation": False,
            "admitted_bw_violation": False,
            "admitted_msd_violation": True,
            "total_latency_ms": 1.0,
            "latency_threshold_ms": 10.0,
        }, 1.0)
        metrics.collect({"accepted": True, "total_latency_ms": 1.0,
                         "latency_threshold_ms": 10.0}, 1.0)
        metrics.collect({"accepted": False, "rejection_reason": "msd",
                         "msd_violation": True, "total_latency_ms": 1.0,
                         "latency_threshold_ms": 10.0}, -20.0)
        row = metrics.row()
        self.assertEqual(row["proposed_cpu_violation_rate"], 100.0 / 3)
        self.assertEqual(row["attempted_msd_violation_rate"], 200.0 / 3)
        self.assertEqual(row["proposed_hard_violation_rate"], 200.0 / 3)
        self.assertEqual(row["admitted_hard_violation_rate"], 100.0 / 3)
        self.assertEqual(row["safe_acceptance_rate"], 100.0 / 3)
        self.assertEqual(row["runtime_rejection_rate"], 100.0 / 3)
        self.assertEqual(row["primary_msd_rejection_rate"], 100.0 / 3)


if __name__ == "__main__":
    unittest.main()
