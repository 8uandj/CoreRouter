import unittest

import numpy as np

from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import TopologyManager


class OneRequestRepository:
    def get_next_entry(self, step):
        return {"cpu": 1.0, "ram": 1.0, "msd": 1, "service_type": "Data"}


class EnvironmentAdmissionSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.env = JOVDPREnv(
            OneRequestRepository(), RewardCalculator(), TopologyManager("vietnam"),
            episode_length=3,
        )
        self.env.reset(seed=11)

    def test_mask_keeps_valid_candidates_when_another_flow_uses_msd(self):
        place, route = 0, 1
        self.env._current_req = {"cpu": 1.0, "ram": 1.0, "msd": 1, "service_type": "Data"}
        self.env._state[route * 3 + 2] = 1
        mask = self.env.action_masks()
        self.assertTrue(mask[self.env._encode_action(place, route)])

    def test_pair_level_msd_uses_realized_sid_list_depth_without_synthetic_hops(self):
        route = 4  # Vietnam Hue has MSD 4; distant pair would exceed it with hop addition.
        self.env._current_req = {"cpu": 1.0, "ram": 1.0, "msd": 4, "service_type": "Data"}
        self.assertTrue(self.env.action_masks()[self.env._encode_action(0, route)])
        _, _, _, _, info = self.env.step(self.env._encode_action(0, route))
        self.assertTrue(info["accepted"])
        self.assertEqual(info["n_sids"], 4)
        self.assertFalse(info["msd_violation"])

    def test_soft_msd_penalty_applies_even_when_runtime_admission_rejects(self):
        self.env.reward_calc.CPU_OVERFLOW = -20.0
        self.env.reward_calc.MSD_VIOLATION_PENALTY = -7.0
        self.env._current_req = {"cpu": 1.0, "ram": 1.0, "msd": 5, "service_type": "Data"}
        _, reward, _, _, info = self.env.step(self.env._encode_action(0, 4))
        self.assertFalse(info["accepted"])
        self.assertTrue(info["msd_violation"])
        self.assertFalse(info["admitted_msd_violation"])
        self.assertEqual(reward, -27.0)

    def test_mask_exhaustion_remains_all_false(self):
        self.env._current_req = {
            "cpu": 1.0, "ram": 1.0,
            "msd": int(np.max(self.env.node_msd_limits)) + 1,
            "service_type": "Data",
        }
        self.assertFalse(self.env.action_masks().any())

    def test_malformed_and_out_of_range_actions_are_rejected(self):
        for action in (-1, self.env.num_nodes ** 2, [0, self.env.num_nodes], [0.5, 1]):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    self.env.step(action)

    def _traffic_trace(self, scenario, seed, consume_lifecycle_rng=False):
        self.env.traffic_scenario = scenario
        self.env.reset(seed=seed)
        trace = []
        for step in range(100):
            self.env._load_request_for_step(step)
            trace.append(tuple(self.env._current_req[key] for key in ("cpu", "ram", "msd", "service_type")))
            if consume_lifecycle_rng:
                self.env.np_random.integers(1, 1000)
        return trace

    def test_chaos_is_seed_reproducible_and_distinct_from_elephant(self):
        chaos_a = self._traffic_trace("chaos", 123)
        chaos_b = self._traffic_trace("chaos", 123)
        elephant = self._traffic_trace("heavy_tail", 123)
        lifecycle_diverged = self._traffic_trace("chaos", 123, consume_lifecycle_rng=True)
        self.assertEqual(chaos_a, chaos_b)
        self.assertNotEqual(chaos_a, elephant)
        self.assertEqual(chaos_a, lifecycle_diverged)

    def test_shared_admission_boundary_blocks_or_records_resource_violations(self):
        self.env._current_req = {"cpu": 1.0, "ram": 1.0, "msd": 1, "service_type": "Data"}
        self.env._state[0:2] = [100.0, 100.0]
        _, _, _, _, protected = self.env.step(self.env._encode_action(0, 0))
        self.assertFalse(protected["accepted"])
        self.assertTrue(protected["cpu_violation"])
        self.assertTrue(protected["ram_violation"])
        self.assertFalse(protected["admitted_cpu_violation"])
        self.assertEqual(protected["rejection_reason"], "cpu")

        self.env.reset(seed=11)
        self.env._current_req = {"cpu": 1.0, "ram": 1.0, "msd": 1, "service_type": "Data"}
        self.env._state[0:2] = [100.0, 100.0]
        self.env.enforce_resource_constraints = False
        _, _, _, _, unprotected = self.env.step(self.env._encode_action(0, 0))
        self.assertTrue(unprotected["accepted"])
        self.assertTrue(unprotected["admitted_cpu_violation"])
        self.assertTrue(unprotected["admitted_ram_violation"])
        self.assertIsNone(unprotected["rejection_reason"])


if __name__ == "__main__":
    unittest.main()
