"""Regression coverage for selection, fallback, and pre-actuation admission."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.ai.heuristic import ActionChoice, HardConstraintError
from src.core.state_manager import NetworkStateManager
from src.portal.backend.app.services.hybrid_decision import (
    generate_srv6_sids, select_and_reserve,
)


class TestHybridDecision(unittest.TestCase):
    def setUp(self):
        self.request = SimpleNamespace(cpu_req=10.0, ram_req=5.0, msd_req=2)
        self.manager = NetworkStateManager(topology_name="vietnam")
        self.drl_choice = ActionChoice(1, 1, "test_drl")
        self.drl = Mock(return_value=SimpleNamespace(choice=self.drl_choice))

    def decide(self):
        return select_and_reserve(
            self.manager, self.request, self.drl, vnf_name="vnf-test"
        )

    def test_normal_load_reserves_without_loading_drl(self):
        result = self.decide()
        self.assertEqual(result.branch, "heuristic")
        self.drl.assert_not_called()
        self.assertIn("vnf-test", self.manager._pending_reservations)
        self.assertGreater(self.manager.snapshot().state.sum(), 0)

    def test_alert_uses_drl_and_tracks_reservation(self):
        self.manager.set_forecast_alert(True)
        result = self.decide()
        self.assertEqual(result.choice, self.drl_choice)
        self.assertEqual(result.method, "Hybrid:DRL")
        self.drl.assert_called_once_with(self.manager, self.request)
        reservation = self.manager._pending_reservations["vnf-test"]
        self.assertEqual(reservation["v_place"], self.drl_choice.v_place)

    @patch("src.portal.backend.app.services.hybrid_decision.get_decoupled_action")
    def test_heuristic_constraint_failure_falls_back(self, heuristic):
        heuristic.side_effect = HardConstraintError("no feasible heuristic")
        result = self.decide()
        self.assertEqual(result.method, "Hybrid:DRL (Heuristic Fallback)")
        self.drl.assert_called_once()

    @patch("src.portal.backend.app.services.hybrid_decision.get_decoupled_action")
    def test_capacity_race_rechecks_drl_pair_before_returning(self, heuristic):
        heuristic.return_value = ActionChoice(0, 0, "heuristic")
        with patch.object(self.manager, "try_reserve", side_effect=[
            (False, "concurrent capacity change"), (True, None)
        ]) as reserve:
            result = self.decide()
        self.assertEqual(result.method, "Hybrid:DRL (Capacity Fallback)")
        self.assertEqual(reserve.call_count, 2)
        self.assertEqual(reserve.call_args.args, (1, 1, 10.0, 5.0, 2))
        self.assertEqual(reserve.call_args.kwargs, {"vnf_name": "vnf-test"})

    def test_exhausted_drl_admission_fails_closed(self):
        self.manager.set_forecast_alert(True)
        with patch.object(self.manager, "try_reserve", return_value=(False, "MSD exceeded")) as reserve:
            with self.assertRaisesRegex(HardConstraintError, "MSD exceeded"):
                self.decide()
        reserve.assert_called_once()
        self.assertEqual(self.manager.snapshot().state.sum(), 0)

    @patch("src.portal.backend.app.services.hybrid_decision.get_decoupled_action")
    def test_unexpected_policy_errors_do_not_trigger_fallback(self, heuristic):
        heuristic.side_effect = RuntimeError("policy bug")
        with self.assertRaisesRegex(RuntimeError, "policy bug"):
            self.decide()
        self.drl.assert_not_called()
        self.assertEqual(self.manager.snapshot().state.sum(), 0)

    def test_segment_depth_and_node_order(self):
        self.assertEqual(generate_srv6_sids(2, 3, 3), [
            "2001:db8:02:01::1", "2001:db8:03:02::1", "2001:db8:03:03::1"
        ])
        self.assertEqual(len(generate_srv6_sids(2, 3, 1)), 1)


if __name__ == "__main__":
    unittest.main()
