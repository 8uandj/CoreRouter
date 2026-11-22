"""Topology identities shared by the Mininet launcher and HIL realization."""

import re
import hashlib
import json

P4_NODE_COUNT = 10

# Undirected backbone links in infrastructure/sdn/topo_p4.py.
# Node IDs are zero-based Vietnam topology IDs; switch IDs are node IDs + 1.
P4_EDGES = (
    (0, 1), (0, 2), (2, 3), (3, 4), (4, 5),
    (5, 6), (6, 7), (7, 8), (8, 9), (0, 5), (5, 8),
)


def neighbors(node_id):
    """Return deterministic adjacent P4 topology node IDs."""
    return tuple(sorted(
        neighbor
        for left, right in P4_EDGES
        for neighbor in ((right,) if left == node_id else ((left,) if right == node_id else ()))
    ))


def collect_live_p4_port_map(net, switch_names):
    """Read switch egress port/MAC mappings from the running Mininet links.

    The returned keys are ``(switch_name, peer_switch_name)`` for backbone
    links and ``(switch_name, "host")`` for the switch's attached host.
    These values come from the interfaces passed to BMv2 at startup.
    """
    result = {}
    for switch_name in switch_names:
        switch = net.get(switch_name)
        for port, intf in switch.intfs.items():
            if port == 0:
                continue
            link = getattr(intf, "link", None)
            if link is None:
                raise ValueError("live P4 port mapping is missing a link for {}".format(intf.name))
            if link.intf1 is intf:
                peer_intf = link.intf2
            elif link.intf2 is intf:
                peer_intf = link.intf1
            else:
                raise ValueError("live P4 port mapping does not own {}".format(intf.name))

            peer_name = peer_intf.node.name
            if peer_name.startswith("s") and peer_name[1:].isdigit():
                peer_key = peer_name
            elif peer_name.startswith("h") and peer_name[1:].isdigit():
                peer_key = "host"
            else:
                raise ValueError("live P4 port mapping has unknown peer {}".format(peer_name))

            src_mac = intf.MAC()
            dst_mac = peer_intf.MAC()
            if any(not isinstance(mac, str) or not re.fullmatch(
                    r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac)
                   for mac in (src_mac, dst_mac)):
                raise ValueError("live P4 port mapping has invalid MAC on {}".format(intf.name))
            key = (switch_name, peer_key)
            if key in result:
                raise ValueError("live P4 port mapping has duplicate peer {}".format(key))
            result[key] = {
                "out_port": port,
                "dst_mac": dst_mac.lower(),
                "src_mac": src_mac.lower(),
            }
    expected_switches = {"s{}".format(node_id + 1) for node_id in range(P4_NODE_COUNT)}
    if set(switch_names) == expected_switches:
        expected_keys = {
            ("s{}".format(node_id + 1), "host")
            for node_id in range(P4_NODE_COUNT)
        }
        for left, right in P4_EDGES:
            expected_keys.add(("s{}".format(left + 1), "s{}".format(right + 1)))
            expected_keys.add(("s{}".format(right + 1), "s{}".format(left + 1)))
        if set(result) != expected_keys:
            raise ValueError("live P4 port mapping does not match the Vietnam topology")
    return result


def compile_p4_forwarding_rules(switch_path, sid_stack, live_ports):
    """Compile a switch path using only observed ports from Mininet."""
    if (not isinstance(switch_path, (list, tuple))
            or len(switch_path) < 2
            or any(not isinstance(node, int) or isinstance(node, bool) or node < 1
                   or node > P4_NODE_COUNT for node in switch_path)
            or len(set(switch_path)) != len(switch_path)):
        raise ValueError("compiled P4 switch path is invalid")
    expected_sids = tuple("fc00:{}::1".format(node) for node in reversed(switch_path))
    if tuple(sid_stack) != expected_sids:
        raise ValueError("compiled P4 path SID stack is inconsistent")
    if not isinstance(live_ports, dict):
        raise ValueError("live P4 port mapping must be a dictionary")

    def observed_port(key):
        value = live_ports.get(key)
        if not isinstance(value, dict):
            raise ValueError("missing live P4 port mapping for {}".format(key))
        port = value.get("out_port")
        if not isinstance(port, int) or isinstance(port, bool) or port < 1:
            raise ValueError("invalid live P4 port mapping for {}".format(key))
        macs = []
        for field in ("dst_mac", "src_mac"):
            mac = value.get(field)
            if not isinstance(mac, str) or not re.fullmatch(
                    r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac):
                raise ValueError("invalid live P4 port mapping for {}".format(key))
            macs.append(mac.lower())
        return port, macs[0], macs[1]

    rules = []
    for current, following in zip(switch_path, switch_path[1:]):
        switch = "s{}".format(current)
        peer = "s{}".format(following)
        out_port, dst_mac, src_mac = observed_port((switch, peer))
        rules.append({
            "switch": switch,
            "type": "ipv6_route",
            "prefix": "fc00:{}::1".format(following),
            "prefix_len": 128,
            "dst_mac": dst_mac,
            "src_mac": src_mac,
            "out_port": out_port,
        })

    terminal_switch = switch_path[-1]
    terminal_sid = "fc00:{}::1".format(terminal_switch)
    terminal_key = ("s{}".format(terminal_switch), "host")
    out_port, dst_mac, src_mac = observed_port(terminal_key)
    rules.append({
        "switch": terminal_key[0],
        "type": "srv6_end_dx4",
        "sid": terminal_sid,
        "dst_mac": dst_mac,
        "src_mac": src_mac,
        "out_port": out_port,
    })
    return rules


def compute_p4_topology_hash(live_ports, loaded_profile_hashes):
    """Fingerprint the observed link map together with loaded BMv2 profiles."""
    if not isinstance(live_ports, dict) or not live_ports:
        raise ValueError("live P4 port mapping is required for topology identity")
    if not isinstance(loaded_profile_hashes, dict) or not loaded_profile_hashes:
        raise ValueError("loaded P4 profile hashes are required for topology identity")
    for profile_hash in loaded_profile_hashes.values():
        if not isinstance(profile_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", profile_hash):
            raise ValueError("loaded P4 profile hash is invalid")
    ports = [
        {"switch": key[0], "peer": key[1], **live_ports[key]}
        for key in sorted(live_ports)
    ]
    payload = {
        "edges": sorted([list(edge) for edge in P4_EDGES]),
        "live_ports": ports,
        "loaded_profiles": dict(sorted(loaded_profile_hashes.items())),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def detach_mininet_switch_bridges(net, switch_names):
    """Stop passive Mininet bridges while preserving links for BMv2 ports."""
    for switch_name in switch_names:
        net.get(switch_name).stop(deleteIntfs=False)


def install_k8s_route_via_gateway(host, subnet, gateway, interface):
    """Route the K8s CIDR through the host bridge from a Mininet namespace."""
    return host.cmd(
        f"ip route replace {subnet} via {gateway} dev {interface}"
    )
