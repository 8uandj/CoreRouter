import numpy as np
from src.core.state_manager import NetworkStateManager


def test_kubernetes_sync_preserves_real_telemetry_without_synthetic_load():
    manager = NetworkStateManager(topology_name='vietnam')
    manager.update_node_telemetry(0, cpu_util=80, ram_util=70, msd_used=3)
    before = manager.snapshot()
    manager.sync_with_kubernetes([])
    np.testing.assert_array_equal(manager.snapshot().state, before.state)
    manager.sync_with_kubernetes([])
    np.testing.assert_array_equal(manager.snapshot().state, before.state)


def test_empty_sync_does_not_invent_resource_utilization():
    manager = NetworkStateManager(topology_name='vietnam')
    manager.sync_with_kubernetes([])
    assert manager.snapshot().state.sum() == 0


def test_telemetry_cannot_erase_a_pending_reservation():
    manager = NetworkStateManager(topology_name='vietnam')
    manager.update_node_telemetry(0, cpu_util=70, ram_util=60)
    assert manager.try_reserve(0, 1, 20, 20, 2, vnf_name='pending')[0]
    manager.update_node_telemetry(0, cpu_util=70, ram_util=60)
    assert not manager.try_reserve(0, 1, 15, 5, 2)[0]
    manager.sync_with_kubernetes([])
    assert manager.snapshot().state[0, 0] == 90
    manager.release_resources('pending')
    assert manager.snapshot().state[0, 0] == 70


def test_untracked_deployments_do_not_get_fabricated_resource_requirements():
    manager = NetworkStateManager(topology_name='vietnam')
    manager.sync_with_kubernetes([{'id': 'unknown', 'data': {'location': 'hanoi-1'}}])
    accepted, error = manager.try_reserve(0, 1, 1, 1, 2, vnf_name='new')
    assert not accepted
    assert error == 'untracked_deployment_resources'
    assert manager.as_public_dict()['unaccounted_vnfs'] == ['unknown']


def test_partial_msd_telemetry_does_not_mark_missing_cpu_ram_fresh():
    manager = NetworkStateManager(topology_name='vietnam', max_telemetry_age_s=10)
    for node in range(manager.num_nodes):
        manager.update_node_telemetry(node, msd_used=0)
    accepted, error = manager.try_reserve(0, 1, 1, 1, 2)
    assert not accepted
    assert error == 'stale_telemetry'


def test_invalid_telemetry_is_rejected_atomically():
    import pytest
    manager = NetworkStateManager(topology_name='vietnam')
    manager.update_node_telemetry(0, cpu_util=70, ram_util=60)
    before = manager.snapshot()
    for values in ({'cpu_util': 20, 'ram_util': float('nan')},
                   {'cpu_util': float('inf')}, {'ram_util': -1}):
        with pytest.raises(ValueError):
            manager.update_node_telemetry(0, **values)
        assert manager.snapshot().state_version == before.state_version
        np.testing.assert_array_equal(manager.snapshot().state, before.state)
    with pytest.raises(ValueError):
        manager.update_node_telemetry(-1, cpu_util=20)


def test_sync_preserves_actuation_intent_and_tracks_ready_replicas():
    manager = NetworkStateManager(topology_name='vietnam')
    assert manager.try_reserve(0, 1, 10, 5, 2, vnf_name='new')[0]
    manager.mark_actuation_requested('new')
    deployment = {'id': 'new', 'data': {'location': 'hanoi-1'}, 'ready': 0, 'desired': 1}
    manager.sync_with_kubernetes([deployment])
    assert manager._active_vnfs['new']['actuation_requested']
    assert not manager._active_vnfs['new']['deployment_ready']
    assert not manager.release_unactuated_reservation('new')[0]
    deployment['ready'] = 1
    manager.sync_with_kubernetes([deployment])
    assert manager._active_vnfs['new']['deployment_ready']
    manager.sync_with_kubernetes([])
    assert not manager._active_vnfs['new']['deployment_ready']


def test_deployed_ttl_reports_teardown_required_and_retains_ledger_charge():
    manager = NetworkStateManager(topology_name='vietnam')
    assert manager.try_reserve(0, 1, 10, 5, 2, vnf_name='deployed')[0]
    manager.sync_with_kubernetes([{
        'id': 'deployed', 'data': {'location': 'hanoi-1'}, 'desired': 1, 'ready': 1,
    }])

    accepted, reason = manager.release_unactuated_reservation('deployed')

    assert not accepted
    assert reason == 'deployed_teardown_required'
    assert 'deployed' in manager._active_vnfs
    assert manager.snapshot().state[0, 0] == 10
