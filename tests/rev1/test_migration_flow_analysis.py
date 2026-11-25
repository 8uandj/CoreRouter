import unittest

from scripts.hil.analyze_migration_flow import analyze_flow


class MigrationFlowAnalysisTests(unittest.TestCase):
    def test_reports_loss_and_longest_receive_gap(self):
        sent = [{"id": 1, "t": 0.0}, {"id": 2, "t": 1.0},
                {"id": 3, "t": 2.0}, {"id": 4, "t": 3.0}]
        received = [{"id": 1, "t": 0.1}, {"id": 2, "t": 1.1}, {"id": 4, "t": 3.1}]
        events = {"ready": 1.2, "steer_confirmed": 2.2, "old_deleted": 2.8}
        result = analyze_flow(sent, received, events)
        self.assertEqual(result["lost_ids"], [3])
        self.assertEqual(result["longest_receive_gap_s"], 2.0)
        self.assertFalse(result["zero_loss"])

    def test_rejects_empty_or_out_of_order_phase_evidence(self):
        sent = [{"id": 1, "t": 0.0}]
        with self.assertRaises(ValueError):
            analyze_flow(sent, [], {"ready": 1, "steer_confirmed": 2, "old_deleted": 3})
        with self.assertRaises(ValueError):
            analyze_flow(sent, [{"id": 1, "t": 0.1}],
                         {"ready": 3, "steer_confirmed": 2, "old_deleted": 4})

    def test_duplicate_receive_is_not_counted_as_continuity(self):
        sent = [{"id": 1, "t": 0.0}, {"id": 2, "t": 1.0}]
        received = [{"id": 1, "t": 0.1}, {"id": 1, "t": 0.2}]
        events = {"ready": 0.3, "steer_confirmed": 0.4, "old_deleted": 0.5}
        result = analyze_flow(sent, received, events)
        self.assertEqual(result["lost_ids"], [2])
        self.assertEqual(result["duplicate_receive_ids"], [1])


if __name__ == "__main__":
    unittest.main()
