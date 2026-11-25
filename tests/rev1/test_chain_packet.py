import unittest

from scapy.all import Ether, IP, Raw, UDP

from scripts.hil.chain_packet import build_srv6_frame, packet_identity


class ChainPacketTests(unittest.TestCase):
    def test_reencapsulation_preserves_exact_inner_ipv4_bytes(self):
        inner = IP(src="198.18.0.1", dst="198.18.0.2", ttl=64) / UDP(sport=45000, dport=49555) / Raw(b"CRCHAIN|pilot|7")
        original = bytes(inner)
        frame = build_srv6_frame("00:00:00:00:00:01", "00:00:00:00:00:02",
                                 ["fc00:9::1", "fc00:6::1"], original)
        self.assertTrue(bytes(frame).endswith(original))
        self.assertEqual(frame.dst, "00:00:00:00:00:02")

    def test_identity_requires_expected_udp_marker(self):
        inner = IP(src="198.18.0.1", dst="198.18.0.2") / UDP(sport=45000, dport=49555) / Raw(b"CRCHAIN|pilot|7")
        self.assertEqual(packet_identity(inner, "pilot"), 7)
        self.assertIsNone(packet_identity(inner, "another"))
        self.assertIsNone(packet_identity(IP(dst="198.18.0.2") / UDP(dport=49555) / Raw(b"other"), "pilot"))

    def test_outgoing_srv6_frame_is_not_an_incoming_vnf_receipt(self):
        inner = IP(src="198.18.0.1", dst="198.18.0.2") / UDP(sport=45000, dport=49555) / Raw(b"CRCHAIN|pilot|7")
        frame = build_srv6_frame("00:00:00:00:00:01", "00:00:00:00:00:02",
                                 ["fc00:9::1", "fc00:6::1"], bytes(inner))
        self.assertIsNone(packet_identity(Ether(bytes(frame)), "pilot"))


if __name__ == "__main__":
    unittest.main()
