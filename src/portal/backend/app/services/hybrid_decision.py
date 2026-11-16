"""Hybrid action selection and local admission, independent of HTTP/actuation.

The router owns telemetry, forecasting and deployment. This service preserves
the heuristic-to-DRL fallback order and reserves the realized SID depth before
returning a decision. These are pair-level checks, not full-chain validation.
"""

from dataclasses import dataclass
from typing import Callable, List

from src.ai.heuristic import ActionChoice, HardConstraintError, get_decoupled_action


@dataclass(frozen=True)
class HybridDecision:
    choice: ActionChoice
    branch: str
    method: str
    sid_stack: List[str]


def generate_srv6_sids(v_place: int, v_route: int, msd_req: int) -> List[str]:
    """Realize the existing request-level pair as a bounded segment list."""
    sid_count = max(1, int(msd_req))
    nodes = [int(v_place)] + [int(v_route)] * (sid_count - 1)
    return [
        f"2001:db8:{node_id:02x}:{index + 1:02x}::1"
        for index, node_id in enumerate(nodes)
    ]


def node_label(node_id: int, node_names: List[str]) -> dict:
    return {"id": int(node_id), "name": node_names[int(node_id)]}


def location_key(node_name: str) -> str:
    """Map topology names to the city labels used by Tekton manifests."""
    return {
        "Hanoi": "hanoi-1", "HaiPhong": "haiphong-1",
        "NinhBinh": "ninhbinh-1", "Vinh": "vinh-1",
        "Hue": "hue-1", "DaNang": "danang-1",
        "QuyNhon": "quynhon-1", "NhaTrang": "nhatrang-1",
        "HoChiMinh": "hcm-1", "CanTho": "cantho-1",
    }.get(node_name, "auto")


def select_and_reserve(
    state_manager, request, drl_action: Callable, *, vnf_name: str
) -> HybridDecision:
    """Choose a pair and reserve it, retrying a rejected heuristic once via DRL.

    The injected DRL callable has the runtime adapter's get_action signature.
    Only hard-constraint failures select a fallback; unexpected errors propagate.
    """
    branch = "heuristic"
    method = "Hybrid:Heuristic"
    if state_manager.choose_mode().mode == "heuristic":
        try:
            choice = get_decoupled_action(state_manager.snapshot(), request)
        except HardConstraintError:
            choice = drl_action(state_manager, request).choice
            branch = "drl"
            method = "Hybrid:DRL (Heuristic Fallback)"
    else:
        choice = drl_action(state_manager, request).choice
        branch = "drl"
        method = "Hybrid:DRL"

    def reserve(selected):
        sids = generate_srv6_sids(selected.v_place, selected.v_route, request.msd_req)
        accepted, error = state_manager.try_reserve(
            selected.v_place, selected.v_route, request.cpu_req, request.ram_req,
            len(sids), vnf_name=vnf_name,
        )
        return sids, accepted, error

    sid_stack, accepted, error = reserve(choice)
    if not accepted and branch == "heuristic":
        choice = drl_action(state_manager, request).choice
        sid_stack, accepted, error = reserve(choice)
        branch = "drl"
        method = "Hybrid:DRL (Capacity Fallback)"
    if not accepted:
        raise HardConstraintError(error or "Hardware constraints violated.")
    return HybridDecision(choice, branch, method, sid_stack)
