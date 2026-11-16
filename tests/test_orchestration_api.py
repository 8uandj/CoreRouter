"""HTTP regression checks with external integrations replaced by test doubles."""

import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = TestClient = None

from src.ai.heuristic import HardConstraintError
from src.core.state_manager import NetworkStateManager


@unittest.skipIf(TestClient is None, "Install FastAPI and httpx for HTTP checks")
class TestOrchestrationAPI(unittest.TestCase):
    def setUp(self):
        # Import only the router, without loading models or initializing K8s.
        stubs = {}
        for name in [
            "src.ai.dgrl_agent", "src.analytics.ai_forecasting",
            "src.portal.backend.app.containers.service_container",
        ]:
            stubs[name] = ModuleType(name)
        stubs["src.ai.dgrl_agent"].get_dgrl_agent = Mock()
        stubs["src.analytics.ai_forecasting"].get_forecast_service = Mock()
        stubs["src.portal.backend.app.containers.service_container"].container = SimpleNamespace(
            orchestrator=Mock(list_vnfs=Mock(return_value=[]))
        )
        name = "src.portal.backend.app.routers.orchestration_router"
        previous = sys.modules.pop(name, None)
        try:
            with patch.dict(sys.modules, stubs):
                self.router_module = importlib.import_module(name)
        finally:
            sys.modules.pop(name, None)
            if previous is not None:
                sys.modules[name] = previous
        self.manager = NetworkStateManager(topology_name="vietnam")
        self.manager_patch = patch.object(
            self.router_module, "get_state_manager", return_value=self.manager
        )
        self.manager_patch.start()
        self.addCleanup(self.manager_patch.stop)
        app = FastAPI()
        app.include_router(self.router_module.router, prefix="/api")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_success_preserves_nested_and_flat_response(self):
        response = self.client.post("/api/orchestrate", json={})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        for key in ["vnf_name", "placement_node", "routing_node", "srv6_segment_list", "method_used"]:
            self.assertEqual(body[key], body["data"][key])
        self.assertEqual(body["hybrid_branch"], "heuristic")
        self.assertEqual(len(body["srv6_segment_list"]), 2)
        self.router_module.get_dgrl_agent.assert_not_called()

    def test_constraint_exhaustion_returns_409(self):
        with patch.object(self.router_module, "select_and_reserve", side_effect=HardConstraintError("no safe pair")):
            response = self.client.post("/api/orchestrate", json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "NO_SAFE_ACTION")

    def test_unexpected_error_remains_500(self):
        with patch.object(self.router_module, "select_and_reserve", side_effect=RuntimeError("test error")):
            response = self.client.post("/api/orchestrate", json={})
        self.assertEqual(response.status_code, 500)

    def test_invalid_request_is_rejected_before_selection(self):
        with patch.object(self.router_module, "select_and_reserve") as select:
            response = self.client.post("/api/orchestrate", json={"msd_req": 0})
        self.assertEqual(response.status_code, 422)
        select.assert_not_called()
