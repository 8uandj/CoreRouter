import unittest

from scapy.all import IP, UDP

from scripts.hil.chain_send import build_inner_probe
from scripts.hil.chain_packet import packet_identity


class ChainSendTests(unittest.TestCase):
    def test_probe_has_stable_flow_and_distinct_packet_identity(self):
        first = build_inner_probe("pilot", 1)
        second = build_inner_probe("pilot", 2)
        self.assertEqual((first[IP].src, first[IP].dst, first[UDP].sport, first[UDP].dport),
                         (second[IP].src, second[IP].dst, second[UDP].sport, second[UDP].dport))
        self.assertEqual(packet_identity(first, "pilot"), 1)
        self.assertEqual(packet_identity(second, "pilot"), 2)


if __name__ == "__main__":
    unittest.main()
