"""Controller confirmation must fail closed when a switch is unavailable."""
import threading
import unittest
from unittest.mock import Mock

from infrastructure.sdn.controller import SteerState, SDNController


class SteeringAdmissionTests(unittest.TestCase):
    def test_unknown_switch_never_confirms_or_deletes_old_rules(self):
        controller = SDNController.__new__(SDNController)
        known = Mock()
        controller.controllers = {'s1': known}
        controller._steer_lock = threading.Lock()
        controller._steer_execution_lock = threading.Lock()
        controller.confirm_steer_done = True
        controller._steer_state = SteerState.DONE
        accepted = controller.steer(
            'replacement',
            [{'switch': 'missing', 'type': 'srv6_sid', 'sid': 'fc00::1'}],
            [{'switch': 's1', 'type': 'ipv6_route', 'prefix': 'fc00::', 'prefix_len': 64}],
        )
        self.assertFalse(accepted)
        self.assertFalse(controller.confirm_steer_done)
        self.assertEqual(controller._steer_state, SteerState.FAILED)
        known.del_ipv6_route.assert_not_called()

    def test_known_switch_installation_can_confirm(self):
        controller = SDNController.__new__(SDNController)
        known = Mock()
        known.add_srv6_local_sid.return_value = True
        controller.controllers = {'s1': known}
        controller._steer_lock = threading.Lock()
        controller._steer_execution_lock = threading.Lock()
        self.assertTrue(controller.steer('replacement', [
            {'switch': 's1', 'type': 'srv6_sid', 'sid': 'fc00::1'}], []))
        self.assertTrue(controller.confirm_steer_done)
        known.add_srv6_local_sid.assert_called_once_with('fc00::1')

    def test_confirmation_identifies_the_deployment(self):
        controller = SDNController({'s1': 9091})
        controller.controllers['s1'] = Mock()
        controller.controllers['s1'].add_srv6_local_sid.return_value = True
        controller.steer('replacement-a', [
            {'switch': 's1', 'type': 'srv6_sid', 'sid': 'fc00::1'}], [])
        status = controller.get_steer_status()
        self.assertEqual(status.get('new_deploy'), 'replacement-a')
        self.assertTrue(status['confirm_steer_done'])
        controller.steer('replacement-b', [
            {'switch': 'missing', 'type': 'srv6_sid', 'sid': 'fc00::2'}], [])
        status = controller.get_steer_status()
        self.assertEqual(status.get('new_deploy'), 'replacement-b')
        self.assertFalse(status['confirm_steer_done'])

    def test_parallel_steer_cannot_confirm_another_operation(self):
        controller = SDNController({'s1': 9091})
        entered = threading.Event()
        release = threading.Event()
        second_installed = threading.Event()
        known = Mock()
        def install(sid):
            if sid == 'fc00::1':
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('test release timeout')
            else:
                second_installed.set()
            return True
        known.add_srv6_local_sid.side_effect = install
        controller.controllers['s1'] = known
        first = threading.Thread(target=lambda: controller.steer('a', [
            {'switch': 's1', 'type': 'srv6_sid', 'sid': 'fc00::1'}], [], operation_id='op-a'))
        second = threading.Thread(target=lambda: controller.steer('b', [
            {'switch': 's1', 'type': 'srv6_sid', 'sid': 'fc00::2'}], [], operation_id='op-b'))
        first.start()
        self.assertTrue(entered.wait(2))
        second.start()
        try:
            self.assertFalse(second_installed.wait(0.05))
            status = controller.get_steer_status()
            self.assertEqual(status['operation_id'], 'op-a')
            self.assertFalse(status['confirm_steer_done'])
        finally:
            release.set()
            first.join(2)
            second.join(2)
        self.assertEqual(controller.get_steer_status()['operation_id'], 'op-b')

    def test_empty_rules_cannot_confirm_steering(self):
        controller = SDNController({})
        self.assertFalse(controller.steer('replacement', [], [], operation_id='op'))
        self.assertFalse(controller.get_steer_status()['confirm_steer_done'])
        self.assertEqual(controller.get_steer_status()['steer_state'], 'failed')

    def test_install_exception_records_failed_operation(self):
        controller = SDNController({'s1': 9091})
        known = Mock()
        known.add_srv6_local_sid.side_effect = RuntimeError('switch unavailable')
        controller.controllers['s1'] = known
        self.assertFalse(controller.steer('replacement', [
            {'switch': 's1', 'type': 'srv6_sid', 'sid': 'fc00::1'}], [], operation_id='op'))
        status = controller.get_steer_status()
        self.assertEqual(status['operation_id'], 'op')
        self.assertEqual(status['steer_state'], 'failed')
        self.assertFalse(status['confirm_steer_done'])
