import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import numpy as np
from src.core.state_manager import NetworkStateManager
from src.ai.heuristic import _pair_feasible
from src.analytics.benchmark.benchmark_testbed.baseline_simulator import BaselineSimulator


class AdmissionSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.mgr = NetworkStateManager(topology_name='vietnam')

    def reserve(self, name, place=4, route=4, cpu=1, ram=1, depth=4):
        return self.mgr.try_reserve(place, route, cpu, ram, depth, vnf_name=name)[0]

    def test_sid_depth_is_not_consumed_across_independent_flows(self):
        self.assertTrue(self.reserve('a'))
        self.assertTrue(self.reserve('b'))
        self.assertEqual(self.mgr.snapshot().state[4, 2], 4)
        self.mgr.release_resources('a')
        self.assertEqual(self.mgr.snapshot().state[4, 2], 4)
        self.mgr.release_resources('b')
        self.assertEqual(self.mgr.snapshot().state[4, 2], 0)

    def test_routing_only_node_does_not_allocate_vnf_cpu_or_memory(self):
        self.mgr._state[1, :2] = 100
        req = SimpleNamespace(cpu_req=10, ram_req=5, msd_req=2)
        self.assertTrue(_pair_feasible(self.mgr.snapshot(), 0, 1, req))
        self.assertTrue(self.reserve('a', place=0, route=1, cpu=10, ram=5, depth=2))
        np.testing.assert_array_equal(self.mgr.snapshot().state[1, :2], [100, 100])
        self.mgr.release_resources('a')
        np.testing.assert_array_equal(self.mgr.snapshot().state[1, :2], [100, 100])

    def test_over_depth_rejects_without_mutating_state(self):
        before = self.mgr.snapshot().state
        self.assertFalse(self.reserve('a', depth=5))
        np.testing.assert_array_equal(before, self.mgr.snapshot().state)

    def test_runtime_action_mask_matches_flat_pair_action_space(self):
        request = SimpleNamespace(cpu_req=10, ram_req=5, msd_req=5)
        masks = self.mgr.action_mask(request)
        n = self.mgr.num_nodes

        self.assertEqual(masks.shape, (n * n,))
        self.assertTrue(masks[0 * n + 0])
        self.assertFalse(masks[0 * n + 4])  # Vietnam node 4 has MSD limit 4.

    def test_release_preserves_reported_external_msd(self):
        self.mgr.update_node_telemetry(4, msd_used=2)
        self.assertTrue(self.reserve('a', depth=4))
        self.mgr.release_resources('a')
        self.assertEqual(self.mgr.snapshot().state[4, 2], 2)

    def test_baseline_pair_predicate_uses_placement_resources_and_route_msd(self):
        snapshot = self.mgr.snapshot()
        state = snapshot.state.copy()
        state[1, :2] = 100
        snapshot.state = state
        spec = SimpleNamespace(cpu_req=10, ram_req=5, msd_req=2)
        self.assertEqual(BaselineSimulator._constraint_failure(snapshot, 0, 1, spec), "")
        self.assertEqual(BaselineSimulator._constraint_failure(snapshot, 0, 1,
                         SimpleNamespace(cpu_req=10, ram_req=5, msd_req=100)), "msd_violation")

    def test_invalid_or_nonfinite_inputs_fail_closed(self):
        for kwargs in [dict(cpu=-1), dict(ram=float('nan')), dict(cpu=float('inf')), dict(cpu='1'),
                       dict(depth=0), dict(depth=1.5), dict(place=-1), dict(route=100)]:
            with self.subTest(kwargs=kwargs):
                self.assertFalse(self.reserve('a', **kwargs))
        self.assertEqual(self.mgr.snapshot().state.sum(), 0)

    def test_duplicate_reservation_name_is_not_double_charged(self):
        self.assertTrue(self.reserve('a'))
        before = self.mgr.snapshot().state
        self.assertFalse(self.reserve('a'))
        np.testing.assert_array_equal(before, self.mgr.snapshot().state)

    def test_concurrent_admission_cannot_overbook_cpu(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            accepted = list(pool.map(lambda i: self.reserve(str(i), cpu=10, depth=1), range(20)))
        self.assertEqual(sum(accepted), 10)
        self.assertEqual(self.mgr.snapshot().state[4, 0], 100)

    def test_admission_rejects_decision_from_stale_snapshot_version(self):
        version = self.mgr.snapshot().state_version
        self.mgr.update_node_telemetry(0, cpu_util=0.2)
        before = self.mgr.snapshot().state.copy()
        accepted, error = self.mgr.try_reserve(
            4, 4, 1, 1, 2, "stale-vnf", expected_state_version=version
        )
        self.assertFalse(accepted)
        self.assertEqual(error, "stale_state_version")
        np.testing.assert_array_equal(self.mgr.snapshot().state, before)

    def test_optional_telemetry_ttl_fails_closed_when_any_node_is_stale(self):
        strict = NetworkStateManager(topology_name="vietnam", max_telemetry_age_s=0.01)
        accepted, error = strict.try_reserve(4, 4, 1, 1, 2)
        self.assertFalse(accepted)
        self.assertEqual(error, "stale_telemetry")
        for node in range(strict.num_nodes):
            strict.update_node_telemetry(node, cpu_util=0.1, ram_util=0.1, msd_used=0)
        self.assertTrue(strict.try_reserve(4, 4, 1, 1, 2)[0])
        time.sleep(0.02)
        accepted, error = strict.try_reserve(4, 4, 1, 1, 2)
        self.assertFalse(accepted)
        self.assertEqual(error, "stale_telemetry")

    def test_anonymous_expiry_does_not_free_another_request(self):
        self.assertTrue(self.mgr.try_reserve(4, 4, 1, 1, 4)[0])
        self.assertTrue(self.mgr.try_reserve(4, 4, 1, 1, 4)[0])
        self.mgr.free_resources(4, 4, 1, 1, 4)
        self.assertEqual(self.mgr.snapshot().state[4, 2], 4)
        self.mgr.free_resources(4, 4, 1, 1, 4)
        self.mgr.free_resources(4, 4, 1, 1, 4)
        self.assertEqual(self.mgr.snapshot().state[4, 0], 0)
        self.assertEqual(self.mgr.snapshot().state[4, 2], 0)

    def test_pending_sync_preserves_per_list_depth_and_placement_only_cpu(self):
        self.assertTrue(self.reserve('a', place=0, route=1, cpu=10, depth=4))
        self.assertTrue(self.reserve('b', place=0, route=1, cpu=10, depth=4))
        self.mgr.sync_with_kubernetes([])
        state = self.mgr.snapshot().state
        self.assertEqual(state[0, 0], 20)
        self.assertEqual(state[1, 0], 0)
        self.assertEqual(state[1, 2], 4)


if __name__ == '__main__':
    unittest.main()


def test_pending_reservation_does_not_expire_on_kubernetes_list_absence():
    from unittest.mock import patch
    manager = NetworkStateManager(topology_name='vietnam')
    manager.reset()
    with patch('src.core.state_manager.time.time', return_value=100.0):
        assert manager.try_reserve(0, 1, 80, 70, 2, vnf_name='uncertain')[0]
    with patch('src.core.state_manager.time.time', return_value=300.0):
        manager.sync_with_kubernetes([])
    assert 'uncertain' in manager._pending_reservations
    assert manager.snapshot().state[0, 0] >= 80
    assert not manager.try_reserve(0, 1, 30, 10, 2)[0]


def test_kubernetes_sync_preserves_anonymous_reservations():
    manager = NetworkStateManager(topology_name='vietnam')
    manager.reset()
    assert manager.try_reserve(0, 1, 80, 70, 2)[0]
    manager.sync_with_kubernetes([])
    assert manager.snapshot().state[0, 0] >= 80
    assert manager.snapshot().state[1, 2] >= 2
    assert not manager.try_reserve(0, 1, 30, 10, 2)[0]


def test_disappearing_deployment_list_entry_does_not_release_live_reservation():
    manager = NetworkStateManager(topology_name='vietnam')
    manager.reset()
    assert manager.try_reserve(0, 1, 80, 70, 2, vnf_name='replacement')[0]
    manager.sync_with_kubernetes([{'id': 'replacement', 'data': {'location': 'hanoi-1'}}])
    manager.sync_with_kubernetes([])
    assert manager.snapshot().state[0, 0] >= 80
    assert 'replacement' in manager._active_vnfs
