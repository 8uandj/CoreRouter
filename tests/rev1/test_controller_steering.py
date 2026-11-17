"""Controller confirmation must fail closed when a switch is unavailable."""
import threading
import unittest
from unittest.mock import Mock

from infrastructure.sdn.controller import SteerState, SDNController


class SteeringAdmissionTests(unittest.TestCase):
    def test_compiles_only_admitted_path_using_observed_live_ports(self):
        live_ports = {
            ("s1", "s6"): {"out_port": 4, "dst_mac": "b6:7f:a3:fc:d3:32",
                            "src_mac": "02:60:73:7f:01:05"},
            ("s6", "s9"): {"out_port": 5, "dst_mac": "7e:30:a5:ff:c7:c0",
                            "src_mac": "da:3d:45:6b:fe:6f"},
            ("s9", "host"): {"out_port": 1, "dst_mac": "00:00:00:00:00:09",
                               "src_mac": "e2:39:34:f0:74:7e"},
        }
        profile_hashes = {"s1": "1" * 64, "s6": "6" * 64, "s9": "9" * 64}
        controller = SDNController({"s1": 9091, "s6": 9096, "s9": 9099},
                                   live_port_map=live_ports,
                                   loaded_profile_hashes=profile_hashes)
        p4_hash = controller.get_topology_status()["p4_topology_hash"]

        rules = controller.compile_realization_rules(
            (1, 6, 9), ("fc00:9::1", "fc00:6::1", "fc00:1::1"))

        self.assertEqual([rule["type"] for rule in rules],
                         ["ipv6_route", "ipv6_route", "srv6_end_dx4"])
        self.assertEqual([(rule["switch"], rule.get("out_port")) for rule in rules],
                         [("s1", 4), ("s6", 5), ("s9", 1)])

    def test_steer_installs_compiled_rules_not_caller_supplied_port_values(self):
        live_ports = {
            ("s1", "s6"): {"out_port": 4, "dst_mac": "b6:7f:a3:fc:d3:32",
                            "src_mac": "02:60:73:7f:01:05"},
            ("s6", "s9"): {"out_port": 5, "dst_mac": "7e:30:a5:ff:c7:c0",
                            "src_mac": "da:3d:45:6b:fe:6f"},
            ("s9", "host"): {"out_port": 1, "dst_mac": "00:00:00:00:00:09",
                               "src_mac": "e2:39:34:f0:74:7e"},
        }
        profile_hashes = {"s1": "1" * 64, "s6": "6" * 64, "s9": "9" * 64}
        controller = SDNController({"s1": 9091, "s6": 9096, "s9": 9099},
                                   live_port_map=live_ports,
                                   loaded_profile_hashes=profile_hashes)
        p4_hash = controller.get_topology_status()["p4_topology_hash"]
        for switch in controller.controllers:
            controller.controllers[switch] = Mock()
        self.assertTrue(controller.steer(
            "vnf-voc-smoke", [], [], operation_id="operation-1",
            request_id="request-1", topology_hash="a" * 64,
            profile_id="p4-path-candidate-v1",
            p4_topology_hash=p4_hash,
            switch_path=(1, 6, 9),
            sid_stack=("fc00:9::1", "fc00:6::1", "fc00:1::1")))
        controller.controllers["s1"].add_ipv6_route.assert_called_once_with(
            prefix="fc00:6::1", prefix_len=128, dst_mac="b6:7f:a3:fc:d3:32",
            src_mac="02:60:73:7f:01:05", out_port=4)
        controller.controllers["s6"].add_ipv6_route.assert_called_once_with(
            prefix="fc00:9::1", prefix_len=128, dst_mac="7e:30:a5:ff:c7:c0",
            src_mac="da:3d:45:6b:fe:6f", out_port=5)
        controller.controllers["s9"].add_srv6_end_dx4.assert_called_once_with(
            sid="fc00:9::1", dst_mac="00:00:00:00:00:09",
            src_mac="e2:39:34:f0:74:7e", out_port=1)
        status = controller.get_steer_status()
        self.assertEqual(status["request_id"], "request-1")
        self.assertEqual(status["topology_hash"], "a" * 64)
        self.assertEqual(status["profile_id"], "p4-path-candidate-v1")
        self.assertEqual(status["p4_topology_hash"], p4_hash)

    def test_path_steering_without_admission_identity_fails_before_install(self):
        known = Mock()
        controller = SDNController({"s1": 9091}, live_port_map={})
        controller.controllers["s1"] = known

        self.assertFalse(controller.steer(
            "vnf-voc-smoke", [], [], operation_id="operation-1",
            switch_path=(1, 2), sid_stack=("fc00:2::1", "fc00:1::1")))
        known.add_ipv6_route.assert_not_called()

    def test_path_steering_rejects_topology_hash_mismatch_before_install(self):
        live_ports = {
            ("s1", "s2"): {"out_port": 2, "dst_mac": "02:00:00:00:00:02",
                            "src_mac": "02:00:00:00:00:01"},
            ("s2", "host"): {"out_port": 1, "dst_mac": "00:00:00:00:00:02",
                               "src_mac": "02:00:00:00:02:01"},
        }
        controller = SDNController({"s1": 9091, "s2": 9092},
                                   live_port_map=live_ports,
                                   loaded_profile_hashes={"s1": "a" * 64})
        for switch in controller.controllers:
            controller.controllers[switch] = Mock()

        self.assertFalse(controller.steer(
            "vnf-voc-smoke", [], [], operation_id="operation-1",
            request_id="request-1", topology_hash="b" * 64,
            profile_id="p4-path-candidate-v1", p4_topology_hash="0" * 64,
            switch_path=(1, 2), sid_stack=("fc00:2::1", "fc00:1::1")))
        controller.controllers["s1"].add_ipv6_route.assert_not_called()

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
