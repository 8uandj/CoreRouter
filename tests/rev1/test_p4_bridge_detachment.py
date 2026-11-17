import unittest
from unittest.mock import Mock

from infrastructure.sdn import p4_topology


class P4BridgeDetachmentTests(unittest.TestCase):
    def test_stops_each_ovs_bridge_without_deleting_interfaces(self):
        net = Mock()
        switches = {f"s{i}": Mock() for i in range(1, 4)}
        net.get.side_effect = switches.__getitem__

        detach = getattr(p4_topology, "detach_mininet_switch_bridges", None)
        self.assertIsNotNone(detach, "P4 startup must detach passive OVS bridges")
        detach(net, ["s1", "s2", "s3"])

        self.assertEqual(net.get.call_count, 3)
        for switch in switches.values():
            switch.stop.assert_called_once_with(deleteIntfs=False)

    def test_k8s_subnet_route_uses_bridge_gateway_not_on_link_arp(self):
        host = Mock()

        install_route = getattr(p4_topology, "install_k8s_route_via_gateway", None)
        self.assertIsNotNone(install_route, "Mininet hosts need a routed K8s subnet")
        install_route(host, "10.1.0.0/16", "10.1.240.1", "veth-h9-mn")

        host.cmd.assert_called_once_with(
            "ip route replace 10.1.0.0/16 via 10.1.240.1 dev veth-h9-mn"
        )


if __name__ == "__main__":
    unittest.main()
