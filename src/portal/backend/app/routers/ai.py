from fastapi import APIRouter, BackgroundTasks, HTTPException
import asyncio
import logging
from typing import Dict, List

from src.ai.dgrl_agent import get_dgrl_agent
from src.ai.heuristic import HardConstraintError, get_decoupled_action
from src.core.state_manager import get_state_manager
from src.portal.backend.app.containers.service_container import container
from src.portal.backend.app.models.schemas import SFCRequest

logger = logging.getLogger("AI-Loop")
router = APIRouter(tags=["AI Simulation"])
orchestration_router = APIRouter(tags=["Hybrid Orchestration"])

AI_STATE = {
    "running": False,
    "current_score": 0.0,
    "status": "NORMAL",
    "logs": []
}

def generate_demo_data():
    data = []
    # NORMAL
    for _ in range(5):
        data.append([0.01, 1, 120, 240, 5])
    # ATTACK
    for _ in range(20):
        data.append([5.5, 1, 9500, 8800, 500])
    # RECOVERY
    for _ in range(5):
        data.append([0.02, 1, 110, 250, 4])
    return data

async def replay_traffic_loop():
    dataset = generate_demo_data()
    logger.info(f"Starting Traffic Replay with {len(dataset)} samples.")

    try:
        for index, features in enumerate(dataset):
            if not AI_STATE["running"]: 
                break
            
            result, score = container.ai_service.predict_and_react(features)
            
            AI_STATE["current_score"] = float(score)
            AI_STATE["status"] = result
            
            log_entry = f"Time: {index}s | AI: {result} (MSE: {score:.4f})"
            AI_STATE["logs"].append(log_entry)
            if len(AI_STATE["logs"]) > 10: 
                AI_STATE["logs"].pop(0)
            
            await asyncio.sleep(1.5)

    except Exception as e:
        logger.error(f"Error in simulation loop: {e}")
    
    AI_STATE["running"] = False
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    AI_STATE["logs"].append("System Standby.")

@router.post("/simulation/start")
def start_simulation(background_tasks: BackgroundTasks):
    if AI_STATE["running"]: 
        return {"status": "running", "message": "Simulation already running"}
    
    AI_STATE["running"] = True
    AI_STATE["logs"] = []
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    
    background_tasks.add_task(replay_traffic_loop)
    return {"status": "started", "message": "Traffic Replay STARTED"}

@router.post("/simulation/stop")
def stop_simulation():
    AI_STATE["running"] = False
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    AI_STATE["logs"].append("Stopped by User.")
    return {"status": "stopped", "message": "Stopping Simulation..."}

@router.get("/status")
def get_ai_status():
    agent = get_dgrl_agent()
    model = agent._load_model()
    
    status_dict = dict(AI_STATE)
    model_loaded = (model is not None and model != "SHADOW_MODE_ACTIVE")
    
    dgrl_status = "loaded" if model_loaded else ("shadow_mode" if model == "SHADOW_MODE_ACTIVE" else "error")
    if agent.load_error:
        dgrl_status = "error"
        
    status_dict.update({
        "model_loaded": model_loaded,
        "model_version": "v11",
        "dgrl_status": dgrl_status,
        "model_path": agent.model_path,
        "scaler_path": agent.scaler_path,
        "load_error": agent.load_error,
    })
    return status_dict


def _generate_srv6_sids(v_place: int, v_route: int, msd_req: int) -> List[str]:
    """Generate a bounded SRv6 segment list for the selected action."""
    sid_count = max(1, int(msd_req))
    nodes = [int(v_place)]
    if sid_count > 1:
        nodes.extend([int(v_route)] * (sid_count - 1))
    return [
        f"2001:db8:{node_id:02x}:{idx + 1:02x}::1"
        for idx, node_id in enumerate(nodes[:sid_count])
    ]


def _node_label(node_id: int, node_names: List[str]) -> Dict[str, object]:
    return {"id": int(node_id), "name": node_names[int(node_id)]}


def _location_key(node_name: str) -> str:
    mapping = {
        "Hanoi": "hn",
        "HaiPhong": "hp",
        "NinhBinh": "hn",
        "Vinh": "dn",
        "Hue": "dn",
        "DaNang": "dn",
        "QuyNhon": "dn",
        "NhaTrang": "hcm",
        "HoChiMinh": "hcm",
        "CanTho": "hcm",
    }
    return mapping.get(node_name, "auto")


@orchestration_router.post("/orchestrate")
def orchestrate_sfc(request: SFCRequest):
    """Adaptive Hybrid Orchestration endpoint.

    Normal load uses the latency-optimized heuristic branch.  Stress load,
    forecast alerts, or heuristic hard-constraint failures engage JO-VPPM.
    """
    state_manager = get_state_manager()
    forecast_alert = bool(
        request.alert_flag
        or request.is_ddos_spike
        or request.service_type.lower() == "attack"
    )
    state_manager.set_forecast_alert(forecast_alert)

    gate = state_manager.choose_mode()
    method = "Heuristic (Latency Optimized)"
    branch = "heuristic"
    fallback_reason = None
    model_loaded = False

    try:
        if gate.mode == "heuristic":
            try:
                choice = get_decoupled_action(state_manager.snapshot(), request)
            except HardConstraintError as exc:
                fallback_reason = str(exc)
                dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
                choice = dgrl_decision.choice
                model_loaded = dgrl_decision.model_loaded
                branch = "drl"
                method = "JO-VPPM AI (Heuristic Hard-Constraint Fallback)"
                fallback_reason = fallback_reason or dgrl_decision.fallback_reason
        else:
            dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
            choice = dgrl_decision.choice
            model_loaded = dgrl_decision.model_loaded
            fallback_reason = dgrl_decision.fallback_reason
            branch = "drl"
            method = "JO-VPPM AI (Resilience Optimized)"

        sid_stack = _generate_srv6_sids(choice.v_place, choice.v_route, request.msd_req)
        accepted, error = state_manager.reserve_resources(
            choice.v_place,
            choice.v_route,
            request.cpu_req,
            request.ram_req,
            len(sid_stack),
        )

        if not accepted and branch == "heuristic":
            fallback_reason = error
            dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
            choice = dgrl_decision.choice
            model_loaded = dgrl_decision.model_loaded
            branch = "drl"
            method = "JO-VPPM AI (Concurrent-State Fallback)"
            sid_stack = _generate_srv6_sids(choice.v_place, choice.v_route, request.msd_req)
            accepted, error = state_manager.reserve_resources(
                choice.v_place,
                choice.v_route,
                request.cpu_req,
                request.ram_req,
                len(sid_stack),
            )

        if not accepted:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "error",
                    "code": "NO_SAFE_ACTION",
                    "message": error or "No safe placement/routing pair satisfies hard constraints.",
                },
            )

    except HardConstraintError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "code": "NO_SAFE_ACTION",
                "message": str(exc),
            },
        ) from exc

    public_state = state_manager.as_public_dict()
    node_names = [node["name"] for node in public_state["nodes"]]
    placement = _node_label(choice.v_place, node_names)
    route = _node_label(choice.v_route, node_names)
    migration_result = None

    if branch == "drl" and public_state["alert_flag"]:
        try:
            migration_result = container.orchestrator.trigger_deploy(
                name=f"proactive-{request.flow_id or placement['name']}".lower().replace("_", "-").replace(" ", "-")[:40],
                vnf_type="firewall" if request.service_type.lower() == "attack" else "router",
                profile="performance",
                location=_location_key(str(placement["name"])),
            )
        except Exception as exc:
            logger.error("Proactive migration trigger failed: %s", exc)
            migration_result = {"status": "error", "message": str(exc)}

    data = {
        "placement_node": placement,
        "routing_node": route,
        "srv6_segment_list": sid_stack,
        "method_used": method,
        "hybrid_branch": branch,
        "gate_reason": gate.reason,
        "action_reason": choice.reason,
        "fallback_reason": fallback_reason,
        "model_loaded": model_loaded,
        "global_utilization": public_state["global_utilization"],
        "avg_cpu": public_state["avg_cpu"],
        "avg_msd_usage": public_state["avg_msd_usage"],
        "alert_flag": public_state["alert_flag"],
        "make_before_break": bool(branch == "drl" and public_state["alert_flag"]),
        "migration_result": migration_result,
        "state": public_state,
    }
    return {
        "status": "success",
        "message": f"Hybrid orchestration selected {method}.",
        "data": data,
        # Compatibility with scripts expecting the flat pseudo-code shape.
        "placement_node": placement,
        "srv6_segment_list": sid_stack,
        "method_used": method,
    }


@orchestration_router.get("/orchestrate/state")
def get_hybrid_state():
    state = get_state_manager().as_public_dict()
    return {"status": "success", "message": "Hybrid state snapshot", "data": state}


@orchestration_router.post("/orchestrate/reset")
def reset_hybrid_state():
    get_state_manager().reset()
    return {"status": "success", "message": "Hybrid state reset", "data": get_state_manager().as_public_dict()}
