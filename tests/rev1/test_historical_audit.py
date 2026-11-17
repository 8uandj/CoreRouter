import importlib.util
import math
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/rev1/audit_historical_results.py'


class HistoricalAuditTests(unittest.TestCase):
    def summarize(self, rows, ddof=1):
        self.assertTrue(SCRIPT.exists(), 'Historical audit tool must exist')
        spec = importlib.util.spec_from_file_location('historical_audit', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.summarize_rows(rows, ['topology', 'scenario', 'variant'],
                                     ['safe_acceptance_rate'], [42, 100], ddof)

    def rows(self):
        return [dict(topology='vietnam', scenario='uniform', variant='full', seed=s,
                     safe_acceptance_rate=v) for s, v in [(42, 10), (100, 14)]]

    def test_recomputes_mean_and_sample_sd_from_independent_seeds(self):
        row = self.summarize(self.rows())[0]
        self.assertEqual(row['safe_acceptance_rate_mean'], 12)
        self.assertAlmostEqual(row['safe_acceptance_rate_std'], math.sqrt(8))
        self.assertEqual(row['n_seeds'], 2)

    def test_benchmark_population_sd_is_explicit(self):
        self.assertEqual(self.summarize(self.rows(), ddof=0)[0]['safe_acceptance_rate_std'], 2)

    def test_duplicate_seed_is_not_an_additional_run(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.summarize(self.rows() + [self.rows()[0]])

    def test_missing_seed_does_not_become_a_zero_result(self):
        with self.assertRaisesRegex(ValueError, 'seed coverage'):
            self.summarize(self.rows()[:1])

    def test_nan_and_infinite_metrics_are_rejected(self):
        for invalid in ['nan', 'inf', '-inf', '']:
            with self.subTest(invalid=invalid):
                rows = self.rows()
                rows[0]['safe_acceptance_rate'] = invalid
                with self.assertRaises(ValueError):
                    self.summarize(rows)

    def test_no_rows_cannot_verify_an_experiment(self):
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.summarize([])


if __name__ == '__main__':
    unittest.main()
