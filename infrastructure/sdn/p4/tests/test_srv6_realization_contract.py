"""Reference-model tests for the HIL's RFC-ordered SRH wire contract."""

import unittest


def sid_for_switch(switch_id):
    return "fc00:{}::1".format(switch_id)


def packet_state_for_path(switch_path):
    # RFC 8754 order: segment_list[0] is final; the last entry is first hop.
    sid_list = tuple(sid_for_switch(switch_id) for switch_id in reversed(switch_path))
    return sid_list, sid_list[-1], len(sid_list) - 1


def advance(sid_list, destination, segments_left):
    if segments_left == 0:
        return destination, segments_left, True
    segments_left -= 1
    return sid_list[segments_left], segments_left, False


class TestSrv6RealizationContract(unittest.TestCase):
    def test_three_switch_wire_order_and_progression(self):
        sid_list, destination, segments_left = packet_state_for_path((1, 3, 4))
        self.assertEqual(sid_list, ("fc00:4::1", "fc00:3::1", "fc00:1::1"))
        self.assertEqual((destination, segments_left), ("fc00:1::1", 2))

        seen = []
        while segments_left > 0:
            seen.append(destination)
            destination, segments_left, terminal = advance(sid_list, destination, segments_left)
            self.assertFalse(terminal)
        seen.append(destination)
        self.assertEqual(seen, ["fc00:1::1", "fc00:3::1", "fc00:4::1"])
        destination, segments_left, terminal = advance(sid_list, destination, segments_left)
        self.assertTrue(terminal)
        self.assertEqual((destination, segments_left), ("fc00:4::1", 0))

    def test_two_switch_path_has_source_and_terminal_sid(self):
        sid_list, destination, segments_left = packet_state_for_path((1, 6))
        self.assertEqual(sid_list, ("fc00:6::1", "fc00:1::1"))
        self.assertEqual((destination, segments_left), ("fc00:1::1", 1))
        destination, segments_left, terminal = advance(sid_list, destination, segments_left)
        self.assertEqual((destination, segments_left, terminal), ("fc00:6::1", 0, False))
        _, _, terminal = advance(sid_list, destination, segments_left)
        self.assertTrue(terminal)


if __name__ == "__main__":
    unittest.main()
