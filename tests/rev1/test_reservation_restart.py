import numpy as np
import pytest
from src.core.state_manager import NetworkStateManager


def test_restart_restores_resources_and_actuation_intent(tmp_path):
    path = tmp_path / 'reservations.sqlite3'
    manager = NetworkStateManager(topology_name='vietnam', reservation_path=path)
    manager.update_node_telemetry(0, cpu_util=40, ram_util=30, msd_used=1)
    assert manager.try_reserve(0, 1, 30, 20, 3, vnf_name='replacement')[0]
    assert manager.try_reserve(0, 1, 5, 5, 2)[0]
    manager.mark_actuation_requested('replacement')
    expected = manager.snapshot().state.copy()
    manager.close()
    restored = NetworkStateManager(topology_name='vietnam', reservation_path=path)
    np.testing.assert_array_equal(restored.snapshot().state, expected)
    assert not restored.try_reserve(0, 1, 30, 1, 2)[0]
    assert not restored.release_unactuated_reservation('replacement')[0]
    assert restored.snapshot().telemetry_age_s[0] is None
    restored.close()


def test_exclusive_ledger_owner_and_topology_mismatch_fail_startup(tmp_path):
    path = tmp_path / 'reservations.sqlite3'
    manager = NetworkStateManager(topology_name='vietnam', reservation_path=path)
    with pytest.raises(RuntimeError, match='owner'):
        NetworkStateManager(topology_name='vietnam', reservation_path=path)
    manager.close()
    with pytest.raises(ValueError, match='topology'):
        NetworkStateManager(topology_name='nsfnet', reservation_path=path)


def test_release_is_durable_and_storage_failure_latches_admission_closed(tmp_path):
    from unittest.mock import patch
    path = tmp_path / 'reservations.sqlite3'
    manager = NetworkStateManager(topology_name='vietnam', reservation_path=path)
    assert manager.try_reserve(0, 1, 10, 5, 2, vnf_name='old')[0]
    manager.release_resources('old')
    manager.close()
    restored = NetworkStateManager(topology_name='vietnam', reservation_path=path)
    assert 'old' not in restored._active_vnfs
    with patch.object(restored._reservation_store, 'save', side_effect=OSError('disk error')):
        with pytest.raises(RuntimeError, match='persistence'):
            restored.try_reserve(0, 1, 10, 5, 2, vnf_name='unconfirmed')
    assert restored.try_reserve(0, 1, 1, 1, 2)[1] == 'reservation_persistence_unavailable'
    restored.close()


def test_process_crash_after_acknowledged_admission_preserves_charge(tmp_path):
    import subprocess
    import sys
    path = tmp_path / 'crash.sqlite3'
    program = '''
import os, sys
from src.core.state_manager import NetworkStateManager
manager = NetworkStateManager(topology_name='vietnam', reservation_path=sys.argv[1])
assert manager.try_reserve(0, 1, 80, 50, 2, vnf_name='crash-vnf')[0]
manager.mark_actuation_requested('crash-vnf')
os._exit(0)
'''
    subprocess.run([sys.executable, '-c', program, str(path)], check=True, timeout=15)
    restored = NetworkStateManager(topology_name='vietnam', reservation_path=path)
    assert restored.snapshot().state[0, 0] == 80
    assert not restored.try_reserve(0, 1, 30, 1, 2)[0]
    assert not restored.release_unactuated_reservation('crash-vnf')[0]
    restored.close()


def test_corrupt_profile_fails_startup_instead_of_empty_ledger(tmp_path):
    import json
    import sqlite3
    path = tmp_path / 'corrupt.sqlite3'
    manager = NetworkStateManager(topology_name='vietnam', reservation_path=path)
    manager.close()
    with sqlite3.connect(path) as db:
        payload = json.loads(db.execute('SELECT payload FROM reservation_snapshot').fetchone()[0])
        payload['active'] = {'broken': {'v_place': -1, 'v_route': 0, 'cpu_req': 10,
                                       'ram_req': 5, 'msd_req': 2}}
        db.execute('UPDATE reservation_snapshot SET payload = ?', (json.dumps(payload),))
    with pytest.raises(ValueError, match='profile'):
        NetworkStateManager(topology_name='vietnam', reservation_path=path)


def test_fork_inherited_manager_cannot_write_under_parent_owner(tmp_path):
    import os
    from unittest.mock import patch
    manager = NetworkStateManager(topology_name='vietnam', reservation_path=tmp_path / 'owner.sqlite3')
    parent_pid = os.getpid()
    with patch('src.core.reservation_store.os.getpid', return_value=parent_pid + 1):
        with pytest.raises(RuntimeError, match='persistence'):
            manager.try_reserve(0, 1, 10, 5, 2)
    assert manager.try_reserve(0, 1, 1, 1, 2)[1] == 'reservation_persistence_unavailable'
    manager.close()
