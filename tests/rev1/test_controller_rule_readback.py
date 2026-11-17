import unittest

from infrastructure.sdn.controller import parse_table_dump, table_entry_matches


ROUTE_DUMP = """Obtaining JSON from switch...
Done
TABLE ENTRIES
**********
Dumping entry 0x0
Match key:
* ipv6.dstAddr        : LPM       fc000006000000000000000000000001/128
Action entry: SRv6Ingress.ipv6_forward - 020000000021, 020000000012, 02
==========
Dumping default entry
Action entry: SRv6Ingress.drop -
==========
"""

LOCAL_SID_DUMP = """TABLE ENTRIES
**********
Dumping entry 0x0
Match key:
* ipv6.dstAddr        : EXACT     fc000001000000000000000000000001
Action entry: SRv6Ingress.srv6_advance_segment -
==========
Dumping default entry
Action entry: SRv6Ingress.drop -
"""

END_DX4_DUMP = """TABLE ENTRIES
**********
Dumping entry 0x0
Match key:
* ipv6.dstAddr        : EXACT     fc000009000000000000000000000001
Action entry: SRv6Ingress.srv6_end_dx4 - 09, 8aade947ad01, 01
==========
Dumping default entry
Action entry: SRv6Ingress.drop -
"""

ROUTE_PORT_TEN_DUMP = ROUTE_DUMP.replace(
    "020000000021, 020000000012, 02",
    "020000000021, 020000000012, 0a",
)


class ControllerRuleReadbackTests(unittest.TestCase):
    def test_parser_canonicalizes_ipv6_macs_and_port(self):
        entries = parse_table_dump(ROUTE_DUMP)
        self.assertEqual(entries, [{
            "index": "0x0",
            "match_field": "ipv6.dstAddr",
            "match_type": "lpm",
            "match_value": "fc00:6::1/128",
            "prefix_len": 128,
            "action_name": "ipv6_forward",
            "action_params": ["020000000021", "020000000012", "2"],
        }])

    def test_exact_route_rule_matches_full_action_and_parameters(self):
        entry = parse_table_dump(ROUTE_DUMP)[0]
        self.assertTrue(table_entry_matches(
            entry, "fc00:6::1", "lpm", "ipv6_forward",
            ["02:00:00:00:00:21", "02:00:00:00:00:12", 2],
        ))
        self.assertFalse(table_entry_matches(
            entry, "fc00:6::1", "lpm", "ipv6_forward",
            ["02:00:00:00:00:21", "02:00:00:00:00:12", 3],
        ))

    def test_cli_hex_port_is_compared_as_decimal_port_number(self):
        entry = parse_table_dump(ROUTE_PORT_TEN_DUMP)[0]
        self.assertEqual(entry["action_params"][-1], "10")
        self.assertTrue(table_entry_matches(
            entry, "fc00:6::1", "lpm", "ipv6_forward",
            ["02:00:00:00:00:21", "02:00:00:00:00:12", 10],
        ))

    def test_exact_local_sid_rule_matches(self):
        entry = parse_table_dump(LOCAL_SID_DUMP)[0]
        self.assertTrue(table_entry_matches(
            entry, "fc00:1::1", "exact", "srv6_advance_segment", []
        ))
        self.assertFalse(table_entry_matches(
            entry, "fc00:1::1", "exact", "drop", []
        ))

    def test_end_dx4_matches_bmv2_trimmed_leading_zero_mac(self):
        entry = parse_table_dump(END_DX4_DUMP)[0]
        self.assertTrue(table_entry_matches(
            entry, "fc00:9::1", "exact", "srv6_end_dx4",
            ["00:00:00:00:00:09", "8a:ad:e9:47:ad:01", 1],
        ))

    def test_malformed_table_dump_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            parse_table_dump("Welcome to runtime CLI\nno table output")
        with self.assertRaisesRegex(ValueError, "entry block"):
            parse_table_dump("TABLE ENTRIES\nDumping entry 0x1\nMatch key:\n")

    def test_duplicate_entries_are_not_single_rule_confirmation(self):
        duplicated = ROUTE_DUMP.replace(
            "Dumping default entry", ROUTE_DUMP.split("Dumping default entry")[0]
            + "==========\nDumping default entry"
        )
        entries = parse_table_dump(duplicated)
        matches = [entry for entry in entries if table_entry_matches(
            entry, "fc00:6::1", "lpm", "ipv6_forward",
            ["02:00:00:00:00:21", "02:00:00:00:00:12", 2],
        )]
        self.assertEqual(len(matches), 2)


if __name__ == "__main__":
    unittest.main()
