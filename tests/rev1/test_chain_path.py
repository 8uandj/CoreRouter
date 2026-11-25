import unittest

from scripts.hil.chain_path import compile_chain_legs


class ChainPathTests(unittest.TestCase):
    def test_compiles_independent_srv6_legs_in_vnf_order(self):
        legs = compile_chain_legs(0, [5, 8], 9, [10] * 10)
        self.assertEqual([leg["node_path"] for leg in legs],
                         [[0, 5], [5, 8], [8, 9]])
        self.assertEqual([leg["sid_stack"] for leg in legs],
                         [["fc00:6::1", "fc00:1::1"],
                          ["fc00:9::1", "fc00:6::1"],
                          ["fc00:10::1", "fc00:9::1"]])

    def test_rejects_switch_profile_below_leg_depth(self):
        limits = [10] * 10
        limits[5] = 1
        with self.assertRaisesRegex(ValueError, "MSD"):
            compile_chain_legs(0, [5, 8], 9, limits)

    def test_rejects_repeated_adjacent_vnf_node(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            compile_chain_legs(0, [5, 5], 9, [10] * 10)


if __name__ == "__main__":
    unittest.main()
