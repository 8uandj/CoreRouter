import unittest

from scripts.hil.analyze_chain_probe import analyze_chain


class ChainAnalysisTests(unittest.TestCase):
    def test_requires_ordered_receipt_at_each_vnf(self):
        events = [
            {"request_id": "r1", "packet_id": 1, "stage": "firewall", "seq": 1, "inner_sha256": "a" * 64},
            {"request_id": "r1", "packet_id": 1, "stage": "idps", "seq": 2, "inner_sha256": "a" * 64},
            {"request_id": "r1", "packet_id": 1, "stage": "egress", "seq": 3, "inner_sha256": "a" * 64},
        ]
        result = analyze_chain("r1", [1], ["firewall", "idps"], events)
        self.assertEqual(result["complete_packets"], 1)
        self.assertEqual(result["invalid_packets"], [])

    def test_reordered_and_missing_receipts_fail(self):
        events = [
            {"request_id": "r1", "packet_id": 1, "stage": "idps", "seq": 1},
            {"request_id": "r1", "packet_id": 1, "stage": "firewall", "seq": 2},
            {"request_id": "r1", "packet_id": 1, "stage": "egress", "seq": 3},
            {"request_id": "r1", "packet_id": 2, "stage": "firewall", "seq": 4},
        ]
        result = analyze_chain("r1", [1, 2], ["firewall", "idps"], events)
        self.assertEqual(result["complete_packets"], 0)
        self.assertEqual(result["invalid_packets"], [1, 2])

    def test_duplicate_or_foreign_receipt_does_not_count(self):
        events = [
            {"request_id": "r1", "packet_id": 1, "stage": "firewall", "seq": 1},
            {"request_id": "r1", "packet_id": 1, "stage": "firewall", "seq": 2},
            {"request_id": "r1", "packet_id": 1, "stage": "idps", "seq": 3},
            {"request_id": "r1", "packet_id": 1, "stage": "egress", "seq": 4},
            {"request_id": "other", "packet_id": 2, "stage": "firewall", "seq": 5},
        ]
        result = analyze_chain("r1", [1, 2], ["firewall", "idps"], events)
        self.assertEqual(result["invalid_packets"], [1, 2])

    def test_modified_inner_packet_fails_chain_integrity(self):
        events = [
            {"request_id": "r1", "packet_id": 1, "stage": "firewall", "seq": 1, "inner_sha256": "a"},
            {"request_id": "r1", "packet_id": 1, "stage": "idps", "seq": 2, "inner_sha256": "b"},
            {"request_id": "r1", "packet_id": 1, "stage": "egress", "seq": 3, "inner_sha256": "a"},
        ]
        self.assertEqual(analyze_chain("r1", [1], ["firewall", "idps"], events)["invalid_packets"], [1])

    def test_missing_hash_cannot_prove_same_inner_packet(self):
        events = [
            {"request_id": "r1", "packet_id": 1, "stage": "firewall", "seq": 1},
            {"request_id": "r1", "packet_id": 1, "stage": "idps", "seq": 2},
            {"request_id": "r1", "packet_id": 1, "stage": "egress", "seq": 3},
        ]
        self.assertEqual(analyze_chain("r1", [1], ["firewall", "idps"], events)["invalid_packets"], [1])

    def test_receipt_must_match_source_inner_packet_hash(self):
        events = [
            {"request_id": "r1", "packet_id": 1, "stage": stage, "seq": seq, "inner_sha256": "a" * 64}
            for seq, stage in enumerate(("firewall", "idps", "egress"), 1)
        ]
        sent = [{"request_id": "r1", "packet_id": 1, "inner_sha256": "b" * 64}]
        self.assertEqual(analyze_chain("r1", [1], ["firewall", "idps"], events, sent)["invalid_packets"], [1])

    def test_duplicate_source_record_is_rejected(self):
        sent = [{"request_id": "r1", "packet_id": 1, "inner_sha256": "a" * 64}] * 2
        with self.assertRaisesRegex(ValueError, "duplicated"):
            analyze_chain("r1", [1], ["firewall", "idps"], [], sent)


if __name__ == "__main__":
    unittest.main()
