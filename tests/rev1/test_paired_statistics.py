import unittest

from src.analytics.benchmark.revision.statistics import paired_statistics


CFG = {"metric": "acceptance_rate", "comparisons": [
    {"name": "harp_vs_saf", "treatment": "harp", "control": "saf_h"}
], "n_bootstrap": 1000, "analysis_seed": 17}


def rows(hash_b="same", values=(70, 60)):
    return [
        {"algorithm": "harp", "topology": "vietnam", "scenario": "chaos", "seed": 42,
         "trace_sha256": "same", "acceptance_rate": values[0]},
        {"algorithm": "saf_h", "topology": "vietnam", "scenario": "chaos", "seed": 42,
         "trace_sha256": hash_b, "acceptance_rate": values[1]},
    ]


class PairedStatisticsTests(unittest.TestCase):
    def test_known_paired_delta_and_all_zero_case(self):
        result = paired_statistics(rows(), CFG)[0]
        self.assertEqual(result["mean_delta"], 10.0)
        self.assertEqual(result["n"], 1)
        zero = paired_statistics(rows(values=(60, 60)), CFG)[0]
        self.assertTrue(zero["all_zero_differences"])
        self.assertEqual(zero["wilcoxon_p"], 1.0)
        self.assertEqual(zero["paired_rank_biserial"], 0.0)

    def test_trace_mismatch_missing_pair_and_nonfinite_fail(self):
        with self.assertRaisesRegex(ValueError, "Trace mismatch"):
            paired_statistics(rows(hash_b="different"), CFG)
        with self.assertRaisesRegex(ValueError, "Unmatched"):
            paired_statistics(rows()[:1], CFG)
        bad = rows()
        bad[0]["acceptance_rate"] = float("nan")
        with self.assertRaisesRegex(ValueError, "non-finite"):
            paired_statistics(bad, CFG)


if __name__ == "__main__":
    unittest.main()
