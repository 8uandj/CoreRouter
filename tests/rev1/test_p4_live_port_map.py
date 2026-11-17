import unittest

from infrastructure.sdn.p4_topology import (
    collect_live_p4_port_map,
    compute_p4_topology_hash,
)


class FakeNode:
    def __init__(self, name):
        self.name = name
        self.intfs = {}


class FakeIntf:
    def __init__(self, name, node, mac, port):
        self.name = name
        self.node = node
        self._mac = mac
        self.port = port
        self.link = None

    def MAC(self):
        return self._mac


class FakeLink:
    def __init__(self, left, right):
        self.intf1 = left
        self.intf2 = right
        left.link = right.link = self


class FakeNet:
    def __init__(self, *nodes):
        self.nodes = {node.name: node for node in nodes}

    def get(self, name):
        return self.nodes[name]


def link(node_a, name_a, mac_a, port_a, node_b, name_b, mac_b, port_b):
    a = FakeIntf(name_a, node_a, mac_a, port_a)
    b = FakeIntf(name_b, node_b, mac_b, port_b)
    node_a.intfs[port_a] = a
    node_b.intfs[port_b] = b
    FakeLink(a, b)


class TestLiveP4PortMap(unittest.TestCase):
    def test_collects_both_directions_and_host_egress_from_mininet_interfaces(self):
        s1, s2, h1, h2 = (FakeNode(name) for name in ("s1", "s2", "h1", "h2"))
        link(s1, "s1-eth1", "02:00:00:00:01:01", 1,
             h1, "h1-eth0", "00:00:00:00:00:01", 0)
        link(s1, "s1-eth2", "02:00:00:00:01:02", 2,
             s2, "s2-eth2", "02:00:00:00:02:02", 2)
        link(s2, "s2-eth1", "02:00:00:00:02:01", 1,
             h2, "h2-eth0", "00:00:00:00:00:02", 0)

        result = collect_live_p4_port_map(FakeNet(s1, s2, h1, h2), ("s1", "s2"))

        self.assertEqual(result, {
            ("s1", "host"): {"out_port": 1, "dst_mac": "00:00:00:00:00:01",
                               "src_mac": "02:00:00:00:01:01"},
            ("s1", "s2"): {"out_port": 2, "dst_mac": "02:00:00:00:02:02",
                            "src_mac": "02:00:00:00:01:02"},
            ("s2", "s1"): {"out_port": 2, "dst_mac": "02:00:00:00:01:02",
                            "src_mac": "02:00:00:00:02:02"},
            ("s2", "host"): {"out_port": 1, "dst_mac": "00:00:00:00:00:02",
                               "src_mac": "02:00:00:00:02:01"},
        })

    def test_rejects_unobserved_or_invalid_mininet_peer_data(self):
        s1, h1 = FakeNode("s1"), FakeNode("h1")
        link(s1, "s1-eth1", "not-a-mac", 1, h1, "h1-eth0", "00:00:00:00:00:01", 0)

        with self.assertRaisesRegex(ValueError, "live P4 port mapping"):
            collect_live_p4_port_map(FakeNet(s1, h1), ("s1",))

    def test_topology_hash_binds_live_port_map_and_loaded_profile_hashes(self):
        ports = {("s1", "s2"): {"out_port": 2,
                                   "dst_mac": "02:00:00:00:00:02",
                                   "src_mac": "02:00:00:00:00:01"}}
        first = compute_p4_topology_hash(ports, {"s1": "a" * 64})
        same = compute_p4_topology_hash(ports, {"s1": "a" * 64})
        changed = compute_p4_topology_hash(ports, {"s1": "b" * 64})

        self.assertEqual(len(first), 64)
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)
        with self.assertRaisesRegex(ValueError, "profile hashes"):
            compute_p4_topology_hash(ports, {})


if __name__ == "__main__":
    unittest.main()
