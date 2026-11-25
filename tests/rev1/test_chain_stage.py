import hashlib
import unittest

from scapy.all import Ether, IP, Raw, UDP

from scripts.hil.chain_stage import process_frame


class ChainStageTests(unittest.TestCase):
    def test_forwarder_preserves_inner_packet_and_records_hash(self):
        inner = IP(src="198.18.0.1", dst="198.18.0.2") / UDP(dport=49555) / Raw(b"CRCHAIN|pilot|7")
        frame = Ether() / inner
        emitted = []
        event = process_frame(frame, "pilot", "firewall", ["fc00:9::1", "fc00:6::1"],
                              "00:00:00:00:00:01", "00:00:00:00:00:02", emitted.append)
        self.assertEqual(event["packet_id"], 7)
        self.assertEqual(event["inner_sha256"], hashlib.sha256(bytes(inner)).hexdigest())
        self.assertEqual(len(emitted), 1)
        self.assertTrue(bytes(emitted[0]).endswith(bytes(inner)))

    def test_other_run_is_not_forwarded(self):
        frame = Ether() / IP() / UDP(dport=49555) / Raw(b"CRCHAIN|other|1")
        emitted = []
        self.assertIsNone(process_frame(frame, "pilot", "firewall", ["fc00:9::1", "fc00:6::1"],
                                        "00:00:00:00:00:01", "00:00:00:00:00:02", emitted.append))
        self.assertEqual(emitted, [])


if __name__ == "__main__":
    unittest.main()
