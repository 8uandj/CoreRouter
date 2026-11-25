"""Plan per-leg SRv6 paths for a testbed chain; does not actuate or admit them."""

from src.portal.backend.app.services.p4_pair_realization import _shortest_path, compile_pair_path


def compile_chain_legs(source_node, vnf_nodes, egress_node, physical_msd_limits):
    if not isinstance(vnf_nodes, (list, tuple)) or len(vnf_nodes) < 2:
        raise ValueError("at least two ordered VNF nodes are required")
    stops = [source_node] + list(vnf_nodes) + [egress_node]
    if any(left == right for left, right in zip(stops, stops[1:])):
        raise ValueError("adjacent VNF and endpoint nodes must be distinct")
    legs = []
    for start, end in zip(stops, stops[1:]):
        path = _shortest_path(start, end)
        leg = compile_pair_path(start, end, end, len(path),
                                physical_msd_limits[end], physical_msd_limits)
        legs.append({"source_node": start, "destination_node": end,
                     "node_path": list(leg.node_path),
                     "switch_path": list(leg.switch_path),
                     "sid_stack": list(leg.sid_stack),
                     "realized_depth": leg.realized_depth})
    return legs
