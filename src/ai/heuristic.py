"""Latency-optimized heuristic branch for RuleDRL orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple, TYPE_CHECKING

import numpy as np

from src.core.state_manager import MAX_CPU, MAX_RAM

if TYPE_CHECKING:
    from src.core.state_manager import NetworkSnapshot

class HardConstraintError(RuntimeError):
    """Raised when a rule-based branch cannot satisfy hardware constraints."""


@dataclass(frozen=True)
class ActionChoice:
    v_place: int
    v_route: int
    reason: str


def _node_feasible(snapshot: NetworkSnapshot, node: int, request: Any) -> bool:
    state = snapshot.state
    msd_limits = snapshot.msd_limits
    return bool(
        state[node, 0] + request.cpu_req <= MAX_CPU
        and state[node, 1] + request.ram_req <= MAX_RAM
        and state[node, 2] + request.msd_req <= msd_limits[node]
    )


def _pair_feasible(snapshot: NetworkSnapshot, v_place: int, v_route: int, request: Any) -> bool:
    touched = {int(v_place), int(v_route)}
    return all(_node_feasible(snapshot, node, request) for node in touched)


def get_decoupled_action(snapshot: NetworkSnapshot, request: Any) -> ActionChoice:
    """Choose the emptiest feasible node, then the shortest feasible 1-hop route."""
    state = snapshot.state
    latency_matrix = snapshot.latency_matrix
    adj_matrix = snapshot.adj_matrix
    num_nodes = len(snapshot.node_names)

    feasible_place = [
        node for node in range(num_nodes)
        if _node_feasible(snapshot, node, request)
    ]
    if not feasible_place:
        raise HardConstraintError("heuristic_no_feasible_placement")

    free_cpu = np.array([MAX_CPU - state[node, 0] for node in feasible_place], dtype=np.float32)
    v_place = int(feasible_place[int(np.argmax(free_cpu))])

    neighbors = [
        int(node) for node in np.where(adj_matrix[v_place] > 0)[0]
        if int(node) != v_place
    ]
    if not neighbors:
        neighbors = [node for node in range(num_nodes) if node != v_place]

    feasible_routes = [
        node for node in neighbors
        if _pair_feasible(snapshot, v_place, node, request)
    ]
    if not feasible_routes and _pair_feasible(snapshot, v_place, v_place, request):
        feasible_routes = [v_place]
    if not feasible_routes:
        raise HardConstraintError("heuristic_msd_or_capacity_route_failed")

    v_route = min(feasible_routes, key=lambda node: float(latency_matrix[v_place][node]))
    return ActionChoice(
        v_place=v_place,
        v_route=int(v_route),
        reason="max_free_cpu_then_shortest_feasible_1hop",
    )


def get_resilience_safe_action(snapshot: NetworkSnapshot, request: Any) -> ActionChoice:
    """Fallback search used when the DRL checkpoint is unavailable."""
    state = snapshot.state
    latency_matrix = snapshot.latency_matrix
    msd_limits = snapshot.msd_limits
    num_nodes = len(snapshot.node_names)

    best_score = -np.inf
    best_pair: Tuple[int, int] | None = None
    for v_place in range(num_nodes):
        for v_route in range(num_nodes):
            if not _pair_feasible(snapshot, v_place, v_route, request):
                continue

            touched = {v_place, v_route}
            min_cpu_headroom = min(MAX_CPU - (state[node, 0] + request.cpu_req) for node in touched)
            min_msd_headroom = min(msd_limits[node] - (state[node, 2] + request.msd_req) for node in touched)
            latency_cost = float(latency_matrix[v_place][v_route])
            spread_bonus = 2.0 if v_place != v_route else 0.0
            score = min_cpu_headroom + (8.0 * min_msd_headroom) + spread_bonus - (0.1 * latency_cost)

            if score > best_score:
                best_score = float(score)
                best_pair = (v_place, v_route)

    if best_pair is None:
        raise HardConstraintError("resilience_no_safe_pair_available")

    return ActionChoice(
        v_place=int(best_pair[0]),
        v_route=int(best_pair[1]),
        reason="resilience_safe_pair_search",
    )
