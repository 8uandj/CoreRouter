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

    def test_unresolved_realization_rejects_before_scheduling_migration(self):
        from src.portal.backend.app.services.realization import AdmittedRealization
        decision = SimpleNamespace(
            choice=SimpleNamespace(v_place=0, v_route=1),
            branch="drl", method="Hybrid:DRL", sid_stack=["2001:db8::1"],
            realization=AdmittedRealization(
                request_id="request-1", operation_id="operation-1",
                topology_hash=self.manager._topology_identity(), profile_id="pair-admission-v1",
                sid_stack=("2001:db8::1",), forwarding_sid=None),
            decision_state_version=0, admission_state_version=1, timings_ms={},
        )
        def reserve_then_return(manager, request, drl, *, vnf_name):
            assert manager.try_reserve(0, 1, 10, 5, 1, vnf_name=vnf_name)[0]
            return decision

        with patch.object(self.router_module, "select_and_reserve", side_effect=reserve_then_return), \
             patch.object(self.router_module, "get_forecast_service"):
            response = self.client.post("/api/orchestrate", json={"alert_flag": True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "UNSUPPORTED_ADMITTED_REALIZATION")
        self.assertEqual(self.manager._active_vnfs, {})

    def test_invalid_request_is_rejected_before_selection(self):
        with patch.object(self.router_module, "select_and_reserve") as select:
            response = self.client.post("/api/orchestrate", json={"msd_req": 0})
        self.assertEqual(response.status_code, 422)
        select.assert_not_called()

    def test_background_migration_status_can_be_retrieved(self):
        record = {'status': 'warning', 'data': {'steer_operation_id': 'operation',
                                               'recovery_state': 'BREAK_UNCONFIRMED'}}
        service = Mock()
        service.get_migration_status.return_value = record
        self.router_module.container.orchestration_service = service
        response = self.client.get('/api/orchestrate/migrations/replacement')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), record)
        service.get_migration_status.assert_called_once_with('replacement')

    def test_unknown_migration_status_is_404(self):
        service = Mock()
        service.get_migration_status.return_value = None
        self.router_module.container.orchestration_service = service
        self.assertEqual(self.client.get('/api/orchestrate/migrations/missing').status_code, 404)

    def test_named_expiry_releases_only_its_reservation_and_is_idempotent(self):
        self.manager.try_reserve(0, 1, 10, 5, 2, vnf_name='first')
        self.manager.try_reserve(0, 1, 10, 5, 2, vnf_name='second')
        payload = {'vnf_name': 'first', 'v_place': 0, 'v_route': 1,
                   'cpu_req': 10, 'ram_req': 5, 'msd_req': 2}
        response = self.client.post('/api/orchestrate/free', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.manager.snapshot().state[0, 0], 10)
        self.assertNotIn('first', self.manager._active_vnfs)
        self.assertIn('second', self.manager._active_vnfs)
        self.assertEqual(self.client.post('/api/orchestrate/free', json=payload).status_code, 200)
        self.assertEqual(self.manager.snapshot().state[0, 0], 10)

    def test_named_expiry_cannot_release_actuation_in_flight(self):
        self.manager.try_reserve(0, 1, 10, 5, 2, vnf_name='replacement')
        self.manager.mark_actuation_requested('replacement')
        response = self.client.post('/api/orchestrate/free', json={
            'vnf_name': 'replacement', 'v_place': 0, 'v_route': 1,
            'cpu_req': 10, 'ram_req': 5, 'msd_req': 2})
        self.assertEqual(response.status_code, 409)
        self.assertIn('replacement', self.manager._active_vnfs)

    def test_benchmark_reset_cannot_clear_live_actuation_charges(self):
        self.manager.try_reserve(0, 1, 10, 5, 2, vnf_name='replacement')
        self.manager.mark_actuation_requested('replacement')
        response = self.client.post('/api/orchestrate/reset')
        self.assertEqual(response.status_code, 409)
        self.assertIn('replacement', self.manager._active_vnfs)
