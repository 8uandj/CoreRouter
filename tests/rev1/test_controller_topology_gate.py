import unittest
from unittest.mock import Mock, patch

from src.portal.backend.app.services.controller_topology import fetch_live_p4_topology_hash


class ControllerTopologyGateTests(unittest.TestCase):
    def test_accepts_only_a_ready_controller_with_the_supported_profile(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "ready": True,
            "profile_id": "p4-path-candidate-v1",
            "p4_topology_hash": "a" * 64,
        }
        requests = Mock(get=Mock(return_value=response))

        with patch.dict("sys.modules", {"requests": requests}):
            result = fetch_live_p4_topology_hash("http://controller/")

        self.assertEqual(result, "a" * 64)
        requests.get.assert_called_once_with("http://controller/topology", timeout=2)

    def test_rejects_unready_or_mismatched_controller_before_admission(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "ready": True,
            "profile_id": "different-profile",
            "p4_topology_hash": "a" * 64,
        }
        requests = Mock(get=Mock(return_value=response))

        with patch.dict("sys.modules", {"requests": requests}):
            with self.assertRaisesRegex(ValueError, "unavailable or mismatched"):
                fetch_live_p4_topology_hash("http://controller")

    def test_missing_controller_url_fails_without_network_access(self):
        with self.assertRaisesRegex(ValueError, "URL is not configured"):
            fetch_live_p4_topology_hash("")


if __name__ == "__main__":
    unittest.main()
