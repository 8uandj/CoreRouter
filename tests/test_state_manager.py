import unittest
import numpy as np
from src.core.state_manager import NetworkStateManager, MAX_CPU

class TestStateManagerHysteresis(unittest.TestCase):
    def setUp(self):
        self.mgr = NetworkStateManager(topology_name="vietnam")
        self.mgr.reset()

    def set_utilization(self, cpu_val):
        # Set all nodes to the same CPU for simplicity to affect global_utilization
        with self.mgr._lock:
            self.mgr._state[:, 0] = cpu_val

    def test_hysteresis_logic(self):
        # 1. Start at 30% -> Expect Heuristic
        self.set_utilization(30.0)
        decision = self.mgr.choose_mode()
        print(f"CPU 30%: mode={decision.mode}, util={decision.global_utilization}")
        self.assertEqual(decision.mode, "heuristic")

        # 2. Increase to 50% -> Expect DRL (Engage at 45%)
        self.set_utilization(50.0)
        decision = self.mgr.choose_mode()
        print(f"CPU 50%: mode={decision.mode}, util={decision.global_utilization}")
        self.assertEqual(decision.mode, "drl")

        # 3. Decrease to 40% -> Expect DRL (Release at 35%, so 40% should hold)
        self.set_utilization(40.0)
        decision = self.mgr.choose_mode()
        print(f"CPU 40%: mode={decision.mode}, util={decision.global_utilization}")
        self.assertEqual(decision.mode, "drl")

        # 4. Decrease to 30% -> Expect Heuristic (Release at 35%)
        self.set_utilization(30.0)
        decision = self.mgr.choose_mode()
        print(f"CPU 30%: mode={decision.mode}, util={decision.global_utilization}")
        self.assertEqual(decision.mode, "heuristic")

    def test_alert_trigger(self):
        # 1. Alert = 1, CPU = 30% -> Expect DRL
        self.set_utilization(30.0)
        self.mgr.set_forecast_alert(True)
        decision = self.mgr.choose_mode()
        self.assertEqual(decision.mode, "drl")
        
        # 2. Alert = 0, CPU = 30% -> Expect Heuristic (since it's below 35%)
        self.mgr.set_forecast_alert(False)
        decision = self.mgr.choose_mode()
        self.assertEqual(decision.mode, "heuristic")

class TestStateManagerSync(unittest.TestCase):
    def setUp(self):
        self.mgr = NetworkStateManager(topology_name="vietnam")
        self.mgr.reset()

    def test_resolve_node_id(self):
        self.assertEqual(self.mgr.resolve_node_id("vnf-nat-hp", "hanoi-1"), 1)
        self.assertEqual(self.mgr.resolve_node_id("vnf-fw-nb", "hanoi-1"), 2)
        self.assertEqual(self.mgr.resolve_node_id("vnf-lb", "hanoi-1"), 0)
        self.assertEqual(self.mgr.resolve_node_id("vnf-vinh", "danang-1"), 3)
        self.assertEqual(self.mgr.resolve_node_id("vnf-hue", "danang-1"), 4)
        self.assertEqual(self.mgr.resolve_node_id("vnf-dn", "danang-1"), 5)
        self.assertEqual(self.mgr.resolve_node_id("vnf-qn", "hcm-1"), 6)
        self.assertEqual(self.mgr.resolve_node_id("vnf-nt", "hcm-1"), 7)
        self.assertEqual(self.mgr.resolve_node_id("vnf-hcm", "hcm-1"), 8)
        self.assertEqual(self.mgr.resolve_node_id("vnf-ct", "hcm-1"), 9)

    def test_sync_with_kubernetes(self):
        self.mgr.sync_with_kubernetes([])
        snap = self.mgr.snapshot()
        for node in snap.nodes:
            self.assertTrue(2.0 <= node["cpu_util"] <= 8.0)
            self.assertTrue(6.0 <= node["ram_util"] <= 10.0)
            self.assertEqual(node["msd_util"], 0.0)

        accepted, error = self.mgr.try_reserve(
            v_place=0, v_route=0, cpu_req=15.0, ram_req=10.0, msd_req=2, vnf_name="vnf-test"
        )
        self.assertTrue(accepted)
        
        self.mgr.sync_with_kubernetes([])
        snap = self.mgr.snapshot()
        node_0 = snap.nodes[0]
        self.assertTrue(17.0 <= node_0["cpu_util"] <= 23.0)

        k8s_vnfs = [{"id": "vnf-test", "data": {"location": "hn"}}]
        self.mgr.sync_with_kubernetes(k8s_vnfs)
        self.assertEqual(len(self.mgr._pending_reservations), 0)
        snap = self.mgr.snapshot()
        node_0 = snap.nodes[0]
        self.assertTrue(17.0 <= node_0["cpu_util"] <= 23.0)

if __name__ == "__main__":
    unittest.main()
