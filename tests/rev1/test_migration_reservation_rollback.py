import asyncio
import unittest

from src.portal.backend.app.services.orchestration_service import OrchestrationService
from src.portal.backend.app.services.realization import AdmittedRealization


class FakeStateManager:
    def __init__(self):
        self.released = []

    def release_resources(self, vnf_name):
        self.released.append(vnf_name)


class FakeOrchestrator:
    def __init__(self, presence, terminate_status="success"):
        self.presence = list(presence)
        self.terminate_status = terminate_status

    def trigger_terminate(self, vnf_name):
        return {"status": self.terminate_status}

    def deployment_presence(self, vnf_name):
        return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]


class MigrationReservationRollbackTests(unittest.TestCase):
    def service(self, presence, terminate_status="success"):
        state = FakeStateManager()
        service = OrchestrationService(
            FakeOrchestrator(presence, terminate_status), None, "",
            state_manager=state, rollback_timeout_s=0.01, rollback_poll_s=0.001,
        )
        return service, state

    def test_releases_only_after_deployment_and_pods_are_confirmed_absent(self):
        service, state = self.service([True, False])
        asyncio.run(service.rollback("replacement-1", "steer rejected"))
        self.assertEqual(state.released, ["replacement-1"])

    def test_keeps_reservation_when_presence_cannot_be_verified(self):
        service, state = self.service([None], terminate_status="error")
        asyncio.run(service.rollback("replacement-2", "terminate unavailable"))
        self.assertEqual(state.released, [])


class MigrationSteeringConfirmationTests(unittest.TestCase):
    @staticmethod
    def admitted_realization(operation_id="current"):
        return AdmittedRealization(
            request_id="request-1", operation_id=operation_id,
            topology_hash="a" * 64, profile_id="profile-1",
            sid_stack=("2001:db8:ffff:1::7531",),
            forwarding_sid="2001:db8:ffff:1::7531")

    def test_missing_admitted_realization_fails_before_make(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        orchestrator = Mock()
        service = OrchestrationService(orchestrator, None, 'http://controller',
                                       state_manager=FakeStateManager())

        result = asyncio.run(service.make_before_break_sequence(
            'old', 'new', 'vnf.yaml', 'hanoi-1', SimpleNamespace()))

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['code'], 'UNSUPPORTED_ADMITTED_REALIZATION')
        orchestrator.trigger_migrate_single.assert_not_called()

    def test_only_matching_completed_operation_can_break_old_vnf(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        import sys

        orchestrator = Mock()
        orchestrator.trigger_migrate_single.return_value = {'status': 'success'}
        orchestrator.break_old_vnf.return_value = {'status': 'success'}
        orchestrator.deployment_presence.return_value = False
        orchestrator.get_replacement_endpoint.return_value = {
            'isReady': True, 'clusterIP': 'fd00::1', 'ports': [{'nodePort': 30001}]}
        service = OrchestrationService(orchestrator, None, 'http://controller',
                                       state_manager=FakeStateManager())
        http = Mock()
        http.post.return_value.status_code = 202
        http.get.return_value.status_code = 200
        responses = [
            {'confirm_steer_done': True},  # legacy/global flag
            {'confirm_steer_done': True, 'new_deploy': 'other', 'operation_id': 'current'},
            {'confirm_steer_done': True, 'new_deploy': 'new', 'operation_id': 'old'},
            {'confirm_steer_done': True, 'new_deploy': 'new', 'operation_id': 'current'},
        ]
        http.get.return_value.json.side_effect = responses
        async def sleep(_):
            orchestrator.break_old_vnf.assert_not_called()
        with patch.dict(sys.modules, {'requests': http}), \
             patch('src.portal.backend.app.services.orchestration_service.asyncio.sleep', side_effect=sleep), \
             patch('uuid.uuid4', return_value='current'):
            result = asyncio.run(service.make_before_break_sequence(
                'old', 'new', 'vnf.yaml', 'hanoi-1', SimpleNamespace(),
                admitted_realization=self.admitted_realization()))
        self.assertEqual(http.get.call_count, 4)
        payload = http.post.call_args.kwargs['json']
        self.assertEqual(payload['operation_id'], 'current')
        orchestrator.break_old_vnf.assert_called_once_with('old')
        self.assertEqual(result['status'], 'success')


class UncertainSteeringTests(unittest.TestCase):
    @staticmethod
    def admitted_realization():
        return MigrationSteeringConfirmationTests.admitted_realization()

    def run_migration(self, submit_error=False, confirmed=False, break_fails=False, old_present=False):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock, AsyncMock, patch
        orchestrator = Mock()
        orchestrator.trigger_migrate_single.return_value = {'status': 'success'}
        orchestrator.break_old_vnf.return_value = {'status': 'success'}
        orchestrator.deployment_presence.return_value = False
        orchestrator.get_replacement_endpoint.return_value = {
            'isReady': True, 'clusterIP': 'fd00::1', 'ports': [{'nodePort': 30001}]}
        orchestrator.break_old_vnf.return_value = {'status': 'error' if break_fails else 'success'}
        orchestrator.deployment_presence.return_value = old_present
        state = FakeStateManager()
        service = OrchestrationService(orchestrator, None, 'http://controller', state_manager=state,
                                       rollback_timeout_s=0.001, rollback_poll_s=0.001)
        http = Mock()
        if submit_error:
            http.post.side_effect = TimeoutError('response lost after submission')
        else:
            http.post.return_value.status_code = 500
        http.get.return_value.status_code = 200
        http.get.return_value.json.return_value = {
            'new_deploy': 'new', 'operation_id': 'current', 'confirm_steer_done': confirmed}
        with patch.dict(sys.modules, {'requests': http}), \
             patch('src.portal.backend.app.services.orchestration_service.asyncio.sleep', new_callable=AsyncMock), \
             patch('uuid.uuid4', return_value='current'):
            result = asyncio.run(service.make_before_break_sequence(
                'old', 'new', 'vnf.yaml', 'hanoi-1', SimpleNamespace(),
                admitted_realization=self.admitted_realization()))
        self.last_service = service
        return result, orchestrator, state

    def test_lost_submit_response_preserves_both_vnfs_and_reservations(self):
        result, orchestrator, state = self.run_migration(submit_error=True)
        orchestrator.trigger_terminate.assert_not_called()
        orchestrator.break_old_vnf.assert_not_called()
        self.assertEqual(state.released, [])
        self.assertEqual(result['status'], 'warning')
        self.assertEqual(result['data']['steer_operation_id'], 'current')
        self.assertEqual(result['data']['recovery_state'], 'STEERING_UNCERTAIN')

    def test_server_error_does_not_prove_rules_were_not_installed(self):
        result, orchestrator, state = self.run_migration()
        orchestrator.trigger_terminate.assert_not_called()
        orchestrator.break_old_vnf.assert_not_called()
        self.assertEqual(state.released, [])
        self.assertEqual(result['status'], 'warning')

    def test_correlated_confirmation_recovers_lost_submit_response(self):
        result, orchestrator, state = self.run_migration(submit_error=True, confirmed=True)
        orchestrator.trigger_terminate.assert_not_called()
        orchestrator.break_old_vnf.assert_called_once_with('old')
        self.assertEqual(result['status'], 'success')


    def test_break_error_is_not_reported_as_completed(self):
        result, orchestrator, state = self.run_migration(confirmed=True, break_fails=True)
        assert result['status'] == 'warning'
        assert result['data']['recovery_state'] == 'BREAK_FAILED'
        assert state.released == []
        assert self.last_service.get_migration_status('new') == result

    def test_accepted_delete_without_absence_keeps_old_reservation(self):
        result, orchestrator, state = self.run_migration(confirmed=True, old_present=True)
        assert result['status'] == 'warning'
        assert result['data']['recovery_state'] == 'BREAK_UNCONFIRMED'
        assert state.released == []

    def test_confirmed_old_absence_releases_only_old_reservation(self):
        result, orchestrator, state = self.run_migration(confirmed=True)
        assert result['status'] == 'success'
        assert state.released == ['old']
        assert self.last_service.get_migration_status('new') == result


if __name__ == "__main__":
    unittest.main()
