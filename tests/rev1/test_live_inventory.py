import json
import subprocess
import unittest

from scripts.hil.live_inventory import InventoryError, collect_inventory, validate_expected_image


class LiveInventoryTests(unittest.TestCase):
    def test_image_drift_blocks_experiment(self):
        with self.assertRaisesRegex(InventoryError, "backend image mismatch"):
            validate_expected_image({"backend_image": "sha256:new"}, "sha256:old")

    def test_failed_command_blocks_inventory(self):
        def run(command):
            return subprocess.CompletedProcess(command, 1, "", "access denied")

        with self.assertRaisesRegex(InventoryError, "docker ps"):
            collect_inventory(run)


    def test_missing_switch_blocks_inventory(self):
        def run(command):
            if command[:2] == ["docker", "ps"]:
                names = ["3s-com-backend"] + [f"bmv2-s{i}" for i in range(1, 10)]
                return subprocess.CompletedProcess(command, 0, "\n".join(names), "")
            raise AssertionError(command)

        with self.assertRaisesRegex(InventoryError, "bmv2-s10"):
            collect_inventory(run)


    def test_complete_inventory_keeps_exact_deployment_count_and_image(self):
        names = ["3s-com-backend"] + [f"bmv2-s{i}" for i in range(1, 11)]

        def run(command):
            if command[:2] == ["docker", "ps"]:
                return subprocess.CompletedProcess(command, 0, "\n".join(names), "")
            if command[:2] == ["docker", "inspect"]:
                return subprocess.CompletedProcess(command, 0, "sha256:abc\n", "")
            if command[:3] == ["kubectl", "-n", "core-router"]:
                items = [{"metadata": {"name": f"vnf-{i}"}, "status": {"readyReplicas": 1, "replicas": 1}}
                         for i in range(17)]
                return subprocess.CompletedProcess(command, 0, json.dumps({"items": items}), "")
            raise AssertionError(command)

        result = collect_inventory(run)
        self.assertEqual(result["backend_image"], "sha256:abc")
        self.assertEqual(result["switches"], [f"bmv2-s{i}" for i in range(1, 11)])
        self.assertEqual(result["deployments"]["count"], 17)
        self.assertEqual(result["deployments"]["ready"], 17)


if __name__ == "__main__":
    unittest.main()
