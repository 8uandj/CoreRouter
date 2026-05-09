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

if __name__ == "__main__":
    unittest.main()
