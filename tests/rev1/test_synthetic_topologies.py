import unittest
from types import SimpleNamespace

import numpy as np

from src.orchestration.jo_vdpr.topology import TopologyManager, SYNTHETIC_TOPOLOGY_SIZES
from src.analytics.benchmark.benchmark_algorithm.run_load_sweep import _seed_active_chains
from src.analytics.benchmark.benchmark_algorithm.config import topologies_for_selection


class SyntheticTopologyTests(unittest.TestCase):
    def test_scalability_selector_runs_matched_10_25_50_100_topology_set(self):
        self.assertEqual(topologies_for_selection("scalability"),
                         ["vietnam", "synthetic_25", "synthetic_50", "synthetic_100"])

    def test_supported_size_sweeps_are_deterministic_connected_grids(self):
        for size in SYNTHETIC_TOPOLOGY_SIZES:
            with self.subTest(size=size):
                first = TopologyManager(f"synthetic_{size}")
                second = TopologyManager(f"synthetic_{size}")
                self.assertEqual(first.num_nodes, size)
                self.assertTrue(first.is_synthetic)
                self.assertEqual(first.names, second.names)
                np.testing.assert_array_equal(first.adj_matrix, second.adj_matrix)
                np.testing.assert_array_equal(first.adj_matrix, first.adj_matrix.T)
                self.assertTrue(np.all(np.diag(first.adj_matrix) == 1.0))
                self.assertEqual(first.get_hop_distance(0, size - 1),
                                 second.get_hop_distance(0, size - 1))
                self.assertTrue(np.all(first.hop_matrix < 99))

    def test_unknown_or_unsupported_synthetic_topology_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "Unsupported synthetic topology size"):
            TopologyManager("synthetic_200")
        with self.assertRaisesRegex(ValueError, "Unknown topology"):
            TopologyManager("made_up")

    def test_active_chain_fixture_seeds_reproducible_background_reservations(self):
        env = SimpleNamespace(
            num_nodes=10, _state=np.zeros(30, dtype=np.float32),
            _link_bw=np.full((10, 10), 10_000.0, dtype=np.float32),
            active_flows=[], EPISODE_LEN=20, max_cpu=100.0, max_ram=100.0,
        )
        _seed_active_chains(env, 25)
        self.assertEqual(len(env.active_flows), 25)
        self.assertAlmostEqual(float(env._state[::3].sum()), 50.0)
        self.assertAlmostEqual(float(env._state[1::3].sum()), 50.0)
        self.assertTrue(all(flow["ttl"] == 41 for flow in env.active_flows))
        self.assertTrue(np.allclose(env._link_bw, env._link_bw.T))

    def test_active_chain_fixture_rejects_resource_overcommit(self):
        env = SimpleNamespace(
            num_nodes=2, _state=np.zeros(6, dtype=np.float32),
            _link_bw=np.full((2, 2), 10_000.0, dtype=np.float32),
            active_flows=[], EPISODE_LEN=20, max_cpu=100.0, max_ram=100.0,
        )
        with self.assertRaisesRegex(ValueError, "exceed per-node CPU/RAM capacity"):
            _seed_active_chains(env, 101)


if __name__ == "__main__":
    unittest.main()
