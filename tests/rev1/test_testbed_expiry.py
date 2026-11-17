from unittest.mock import Mock
from src.analytics.benchmark.benchmark_testbed.config import BenchmarkConfig
from src.analytics.benchmark.benchmark_testbed.models import ActiveReservation
from src.analytics.benchmark.benchmark_testbed.runner import ScenarioRunner


def test_expiry_uses_request_identity_and_retains_unconfirmed_release():
    client = Mock()
    client.free.return_value = (409, {'detail': 'cleanup required'}, 1.0)
    runner = ScenarioRunner(BenchmarkConfig(), client)
    reservation = ActiveReservation(1, 0, 1, 10, 5, 2, 'replacement')
    assert runner._expire_reservations(2, [reservation]) == [reservation]
    assert client.free.call_args.args[0]['vnf_name'] == 'replacement'
    client.free.return_value = (200, {'status': 'success'}, 1.0)
    assert runner._expire_reservations(3, [reservation]) == []


def test_readiness_requires_positive_kubernetes_readiness_confirmation():
    client = Mock()
    client.state.side_effect = [
        (200, {'data': {'active_vnfs': [{'name': 'new', 'is_pending': False,
                                       'deployment_ready': False}]}}, 0.0),
        (200, {'data': {'active_vnfs': [{'name': 'new', 'is_pending': False,
                                       'deployment_ready': True}]}}, 0.0),
    ]
    runner = ScenarioRunner(BenchmarkConfig(poll_interval_s=0.001), client)
    _, ready = runner._wait_for_vnf_ready('new', 1.0)
    assert ready
    assert client.state.call_count == 2
