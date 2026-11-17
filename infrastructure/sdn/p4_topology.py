"""Topology identities shared by the Mininet launcher and HIL realization."""

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
