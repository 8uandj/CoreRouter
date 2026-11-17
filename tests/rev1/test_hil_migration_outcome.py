from unittest.mock import Mock
from src.analytics.benchmark.benchmark_testbed.config import BenchmarkConfig
from src.analytics.benchmark.benchmark_testbed.runner import ScenarioRunner


def test_migration_wait_ignores_unrelated_record_and_requires_confirmed_completion():
    client = Mock()
    client.migration_status.side_effect = [
        (200, {'status': 'success', 'data': {'old_vnf': 'old', 'new_vnf': 'other',
            'steer_operation_id': 'other-op', 'steer_status': 'CONFIRMED', 'recovery_state': 'COMPLETED'}}, 0),
        (200, {'status': 'running', 'data': {'old_vnf': 'old', 'new_vnf': 'new',
            'steer_operation_id': 'op', 'recovery_state': 'BREAK_REQUESTING'}}, 0),
        (200, {'status': 'success', 'data': {'old_vnf': 'old', 'new_vnf': 'new',
            'steer_operation_id': 'op', 'steer_status': 'CONFIRMED', 'recovery_state': 'COMPLETED'}}, 0),
    ]
    runner = ScenarioRunner(BenchmarkConfig(poll_interval_s=0.001, migration_timeout_s=1), client)
    _, result = runner._wait_for_migration('old', 'new')
    assert result['status'] == 'success'
    assert result['data']['steer_operation_id'] == 'op'
    assert client.migration_status.call_count == 3
    client.status.assert_not_called()


def test_uncertain_migration_is_a_terminal_recovery_outcome_not_success():
    client = Mock()
    client.migration_status.return_value = (200, {'status': 'warning', 'data': {
        'old_vnf': 'old', 'new_vnf': 'new', 'steer_operation_id': 'op',
        'recovery_state': 'STEERING_UNCERTAIN'}}, 0)
    runner = ScenarioRunner(BenchmarkConfig(poll_interval_s=0.001, migration_timeout_s=1), client)
    _, result = runner._wait_for_migration('old', 'new')
    assert result['status'] == 'warning'
    assert client.migration_status.call_count == 1


def test_completed_record_without_operation_proof_is_not_verified():
    client = Mock()
    client.migration_status.return_value = (200, {'status': 'success', 'data': {
        'old_vnf': 'old', 'new_vnf': 'new', 'recovery_state': 'COMPLETED',
        'steer_status': 'CONFIRMED'}}, 0)
    runner = ScenarioRunner(BenchmarkConfig(poll_interval_s=0.001, migration_timeout_s=1), client)
    _, result = runner._wait_for_migration('old', 'new')
    assert result['completion_verified'] is False
