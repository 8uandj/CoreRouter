"""Hybrid action selection and local admission, independent of HTTP/actuation.

The router owns telemetry, forecasting and deployment. This service preserves
the heuristic-to-DRL fallback order and reserves the realized SID depth before
returning a decision. These are pair-level checks, not full-chain validation.
"""

from dataclasses import dataclass
import time
import uuid
from typing import Callable, List

from src.ai.heuristic import ActionChoice, HardConstraintError, get_decoupled_action
from .realization import AdmittedRealization
from .p4_pair_realization import compile_pair_path


@dataclass(frozen=True)
class HybridDecision:
    choice: ActionChoice
    branch: str
    method: str
    sid_stack: List[str]
    decision_state_version: int
    admission_state_version: int
    timings_ms: dict[str, float]
    realization: AdmittedRealization


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
    decision_start = time.perf_counter()
    branch = "heuristic"
    method = "Hybrid:Heuristic"
    timings: dict[str, float] = {}
    state_start = time.perf_counter()
    mode = state_manager.choose_mode().mode
    snapshot = state_manager.snapshot()
    timings["state_snapshot_ms"] = (time.perf_counter() - state_start) * 1000.0
    expected_state_version = snapshot.state_version
    if mode == "heuristic":
        try:
            policy_start = time.perf_counter()
            choice = get_decoupled_action(snapshot, request)
            timings["heuristic_inference_ms"] = (time.perf_counter() - policy_start) * 1000.0
        except HardConstraintError:
            policy_start = time.perf_counter()
            drl_decision = drl_action(state_manager, request)
            choice = drl_decision.choice
            timings.update(getattr(drl_decision, "timings_ms", {}))
            timings.setdefault("policy_inference_ms", (time.perf_counter() - policy_start) * 1000.0)
            branch = "drl"
            method = "Hybrid:DRL (Heuristic Fallback)"
    else:
        policy_start = time.perf_counter()
        drl_decision = drl_action(state_manager, request)
        choice = drl_decision.choice
        timings.update(getattr(drl_decision, "timings_ms", {}))
        timings.setdefault("policy_inference_ms", (time.perf_counter() - policy_start) * 1000.0)
        branch = "drl"
        method = "Hybrid:DRL"

    source_node = getattr(request, "source_node", None)
    if source_node is None:
        source_node = getattr(request, "ingress_node", None)

    def reserve(selected):
        path = None
        if source_node is None:
            sids = generate_srv6_sids(selected.v_place, selected.v_route, request.msd_req)
        else:
            try:
                if isinstance(source_node, str):
                    if source_node not in snapshot.node_names:
                        raise ValueError("source node name is not in the runtime topology")
                    source_id = snapshot.node_names.index(source_node)
                else:
                    source_id = source_node
                path = compile_pair_path(
                    source_id, selected.v_place, selected.v_route,
                    requested_depth=request.msd_req,
                    route_msd_limit=float(snapshot.msd_limits[selected.v_route]),
                    physical_msd_limits=snapshot.msd_limits.tolist(),
                )
                sids = list(path.sid_stack)
            except (IndexError, TypeError, ValueError) as exc:
                return [], False, str(exc), None
        admission_start = time.perf_counter()
        accepted, error = state_manager.try_reserve(
            selected.v_place, selected.v_route, request.cpu_req, request.ram_req,
            len(sids), vnf_name=vnf_name,
            expected_state_version=expected_state_version,
        )
        timings["admission_validation_ms"] = timings.get("admission_validation_ms", 0.0) + (
            time.perf_counter() - admission_start
        ) * 1000.0
        return sids, accepted, error, path

    sid_stack, accepted, error, path = reserve(choice)
    if not accepted and branch == "heuristic" and error != "stale_state_version":
        policy_start = time.perf_counter()
        drl_decision = drl_action(state_manager, request)
        choice = drl_decision.choice
        timings.update(getattr(drl_decision, "timings_ms", {}))
        timings.setdefault("policy_inference_ms", (time.perf_counter() - policy_start) * 1000.0)
        sid_stack, accepted, error, path = reserve(choice)
        branch = "drl"
        method = "Hybrid:DRL (Capacity Fallback)"
    if not accepted:
        raise HardConstraintError(error or "Hardware constraints violated.")
    timings["decision_policy_and_admission_ms"] = (time.perf_counter() - decision_start) * 1000.0
    return HybridDecision(
        choice, branch, method, sid_stack,
        decision_state_version=expected_state_version,
        admission_state_version=expected_state_version + 1,
        timings_ms=timings,
        realization=AdmittedRealization(
            request_id=vnf_name,
            operation_id=str(uuid.uuid4()),
            topology_hash=state_manager._topology_identity(),
            profile_id="p4-path-candidate-v1" if path is not None else "pair-admission-v1",
            sid_stack=tuple(sid_stack),
            # Path compilation alone is not exact controller rule readback or
            # packet evidence. Keep actuation fail-closed until those gates pass.
            forwarding_sid=None,
        ),
    )
