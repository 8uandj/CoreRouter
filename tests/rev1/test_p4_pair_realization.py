import unittest

from src.portal.backend.app.services.p4_pair_realization import compile_pair_path


class TestP4PairRealization(unittest.TestCase):
    def test_compiles_shortest_verified_p4_path_into_observed_switch_sids(self):
        path = compile_pair_path(
            source_node=0,
            placement_node=5,
            route_node=8,
            requested_depth=2,
            route_msd_limit=10,
            physical_msd_limits=[10, 10, 5, 5, 4, 8, 4, 5, 10, 5],
        )

        self.assertEqual(path.node_path, (0, 5))
        self.assertEqual(path.switch_path, (1, 6))
        self.assertEqual(path.sid_stack, ("fc00:6::1", "fc00:1::1"))
        self.assertEqual(path.realized_depth, 2)
        self.assertEqual(path.route_profile_node, 8)

    def test_shortest_path_uses_deterministic_node_order_for_equal_paths(self):
        path = compile_pair_path(0, 3, 0, requested_depth=3, route_msd_limit=10,
                                 physical_msd_limits=[10, 10, 5, 5, 4, 8, 4, 5, 10, 5])

        self.assertEqual(path.node_path, (0, 2, 3))
        self.assertEqual(path.sid_stack, ("fc00:4::1", "fc00:3::1", "fc00:1::1"))

    def test_realized_path_depth_must_match_requested_sid_depth(self):
        with self.assertRaisesRegex(ValueError, "requested MSD depth"):
            compile_pair_path(0, 5, 8, requested_depth=1, route_msd_limit=10,
                              physical_msd_limits=[10, 10, 5, 5, 4, 8, 4, 5, 10, 5])

    def test_route_profile_msd_is_checked_against_materialized_sid_depth(self):
        with self.assertRaisesRegex(ValueError, "route profile MSD"):
            compile_pair_path(0, 5, 8, requested_depth=2, route_msd_limit=0,
                              physical_msd_limits=[10, 10, 5, 5, 4, 8, 4, 5, 10, 5])
        with self.assertRaisesRegex(ValueError, "exceeds route profile MSD"):
            compile_pair_path(0, 3, 8, requested_depth=3, route_msd_limit=2,
                              physical_msd_limits=[10, 10, 5, 5, 4, 8, 4, 5, 10, 5])

    def test_every_switch_parser_profile_on_path_is_checked(self):
        with self.assertRaisesRegex(ValueError, "physical switch MSD"):
            compile_pair_path(0, 5, 8, requested_depth=2, route_msd_limit=10,
                              physical_msd_limits=[1, 10, 5, 5, 4, 8, 4, 5, 10, 5])

    def test_same_node_pair_is_not_a_forwardable_switch_path(self):
        with self.assertRaisesRegex(ValueError, "distinct ingress and placement"):
            compile_pair_path(8, 8, 8, requested_depth=1, route_msd_limit=10,
                              physical_msd_limits=[10] * 10)

    def test_invalid_node_ids_are_rejected(self):
        cases = [(-1, 1, 0, 1, 10), (0, 10, 0, 1, 10),
                 (0, 1, 10, 1, 10), (True, 1, 0, 1, 10)]
        for source, placement, route, depth, limit in cases:
            with self.subTest(source=source, placement=placement, route=route):
                with self.assertRaisesRegex(ValueError, "node ID"):
                    compile_pair_path(source, placement, route, depth, limit,
                                      physical_msd_limits=[10] * 10)


if __name__ == "__main__":
    unittest.main()
