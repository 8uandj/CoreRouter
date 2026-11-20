"""Compile the approved HIL pair contract onto the observed P4 topology."""

from collections import deque
from dataclasses import dataclass
import math
from numbers import Real
from typing import Tuple

from infrastructure.sdn.p4_topology import (
    P4_NODE_COUNT,
    compile_p4_forwarding_rules,
    neighbors,
)


@dataclass(frozen=True)
class PairPath:
    node_path: Tuple[int, ...]
    switch_path: Tuple[int, ...]
    sid_stack: Tuple[str, ...]
    realized_depth: int
    route_profile_node: int


def _node_id(value, label):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < P4_NODE_COUNT:
        raise ValueError("invalid node ID for " + label)
    return value


def _shortest_path(source, destination):
    queue = deque([(source, (source,))])
    visited = {source}
    while queue:
        current, path = queue.popleft()
        if current == destination:
            return path
        for adjacent in neighbors(current):
            if adjacent not in visited:
                visited.add(adjacent)
                queue.append((adjacent, path + (adjacent,)))
    raise ValueError("no physical P4 path between ingress and placement nodes")


def compile_pair_path(source_node, placement_node, route_node,
                      requested_depth, route_msd_limit, physical_msd_limits):
    """Compile source→placement into the live switch SID namespace.

    The request's MSD depth is exact, matching current pair-level request
    semantics. It may be admitted only when it equals the concrete number of
    switch SIDs and also fits the selected route profile's parser limit.
    """
    source = _node_id(source_node, "source")
    placement = _node_id(placement_node, "placement")
    route = _node_id(route_node, "route profile")
    if source == placement:
        raise ValueError("forwarding requires distinct ingress and placement nodes")
    if (not isinstance(requested_depth, int) or isinstance(requested_depth, bool)
            or requested_depth < 1):
        raise ValueError("requested MSD depth must be a positive integer")
    if (not isinstance(route_msd_limit, Real) or isinstance(route_msd_limit, bool)
            or not math.isfinite(float(route_msd_limit)) or route_msd_limit < 1):
        raise ValueError("route profile MSD limit must be positive and finite")

    if (not isinstance(physical_msd_limits, (list, tuple))
            or len(physical_msd_limits) != P4_NODE_COUNT):
        raise ValueError("physical switch MSD profile must cover all P4 nodes")
    for limit in physical_msd_limits:
        if (not isinstance(limit, Real) or isinstance(limit, bool)
                or not math.isfinite(float(limit)) or float(limit) < 1):
            raise ValueError("physical switch MSD profile contains an invalid limit")

    node_path = _shortest_path(source, placement)
    # RFC 8754 wire ordering: Segment List[0] is the final SID; the final
    # element is the first SID processed (source switch).
    sids = tuple("fc00:{}::1".format(node_id + 1)
                 for node_id in reversed(node_path))
    depth = len(sids)
    if depth != requested_depth:
        raise ValueError(
            "requested MSD depth does not match materialized P4 path depth"
        )
    if depth > float(route_msd_limit):
        raise ValueError("materialized path exceeds route profile MSD limit")
    if any(depth > float(physical_msd_limits[node_id]) for node_id in node_path):
        raise ValueError("materialized path exceeds physical switch MSD profile")

    return PairPath(
        node_path=node_path,
        switch_path=tuple(node_id + 1 for node_id in node_path),
        sid_stack=sids,
        realized_depth=depth,
        route_profile_node=route,
    )


def compile_switch_rules(path, live_ports):
    if not isinstance(path, PairPath):
        raise ValueError("a compiled P4 path is required")
    expected_switches = tuple(node_id + 1 for node_id in path.node_path)
    if (path.switch_path != expected_switches
            or len(path.switch_path) != len(path.sid_stack)
            or len(path.switch_path) < 2):
        raise ValueError("compiled P4 path is internally inconsistent")
    return compile_p4_forwarding_rules(path.switch_path, path.sid_stack, live_ports)
