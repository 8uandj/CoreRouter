import unittest

from src.analytics.benchmark.benchmark_algorithm.config import scenario_jobs


class ScenarioAliasTests(unittest.TestCase):
    def test_elephant_and_burst_map_to_registered_generators(self):
        self.assertEqual(scenario_jobs("elephant_stress", "stress"), [
            ("elephant_stress", "heavy_tail", "stress")
        ])
        self.assertEqual(scenario_jobs("burst_surge", "stress"), [
            ("burst_surge", "bursty", "stress")
        ])

    def test_chaos_has_its_own_generator(self):
        self.assertEqual(scenario_jobs("chaos", "stress"), [("chaos", "chaos", "stress")])

    def test_suite_presets_keep_chaos_distinct_from_elephant(self):
        for scenario in ("thesis", "ablation"):
            with self.subTest(scenario=scenario):
                jobs = scenario_jobs(scenario, "stress")
                self.assertIn(("chaos", "chaos", "stress"), jobs)
                self.assertIn(("elephant_stress", "heavy_tail", "stress"), jobs)

    def test_all_scenario_preset_includes_chaos(self):
        self.assertIn(("chaos", "chaos", "stress"), scenario_jobs("all", "stress"))


if __name__ == "__main__":
    unittest.main()
