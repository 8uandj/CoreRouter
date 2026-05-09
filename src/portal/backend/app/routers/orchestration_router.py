from fastapi import APIRouter, HTTPException, BackgroundTasks
import asyncio
import logging
from typing import Dict, List, Optional

from src.ai.dgrl_agent import get_dgrl_agent
from src.ai.heuristic import HardConstraintError, get_decoupled_action
from src.core.state_manager import get_state_manager
from src.portal.backend.app.containers.service_container import container
from src.portal.backend.app.models.schemas import SFCRequest, MigrateSingleRequest, BreakOldVnfRequest

logger = logging.getLogger("OrchestrationRouter")
router = APIRouter(tags=["Hybrid Orchestration"])

# Global Lock to prevent concurrent Make-Before-Break migrations (Race Condition Protection)
MIGRATION_LOCK = asyncio.Lock()

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

@router.post("/orchestrate")
async def orchestrate_sfc(request: SFCRequest, background_tasks: BackgroundTasks):
    """
    Adaptive Hybrid Orchestration endpoint.
    Receives (source, target, traffic_type) through SFCRequest.
    """
    state_manager = get_state_manager()
    
    # Trigger Forecast Alert if needed
    forecast_alert = bool(
        request.alert_flag 
        or request.is_ddos_spike 
        or request.service_type.lower() == "attack"
    )
    state_manager.set_forecast_alert(forecast_alert)

    gate = state_manager.choose_mode()
    method = "Hybrid:Heuristic"
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
                method = "Hybrid:DRL (Heuristic Fallback)"
        else:
            dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
            choice = dgrl_decision.choice
            model_loaded = dgrl_decision.model_loaded
            branch = "drl"
            method = "Hybrid:DRL"

        sid_stack = _generate_srv6_sids(choice.v_place, choice.v_route, request.msd_req)
        
        # Admission Control
        accepted, error = state_manager.reserve_resources(
            choice.v_place, choice.v_route, request.cpu_req, request.ram_req, len(sid_stack)
        )

        if not accepted:
            # If heuristic failed, try DRL as last resort if not already tried
            if branch == "heuristic":
                dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
                choice = dgrl_decision.choice
                sid_stack = _generate_srv6_sids(choice.v_place, choice.v_route, request.msd_req)
                accepted, error = state_manager.reserve_resources(
                    choice.v_place, choice.v_route, request.cpu_req, request.ram_req, len(sid_stack)
                )
                if accepted:
                    branch = "drl"
                    method = "Hybrid:DRL (Capacity Fallback)"

        if not accepted:
            # Smart Admission Control: Must return 409 NO_SAFE_ACTION
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "error",
                    "code": "NO_SAFE_ACTION",
                    "message": error or "Hardware constraints violated (CPU/RAM/MSD)."
                }
            )

    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Orchestration internal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    public_state = state_manager.as_public_dict()
    node_names = [n["name"] for n in public_state["nodes"]]
    placement = _node_label(choice.v_place, node_names)
    route = _node_label(choice.v_route, node_names)
    
    migration_result = None
    make_before_break = bool(branch == "drl" and forecast_alert)

    # Trigger Make-Before-Break if Alert=1 and DRL is used (Race Condition Protection)
    if make_before_break:
        if MIGRATION_LOCK.locked():
            logger.warning("PHASE 5: Concurrent migration request blocked by lock.")
            migration_result = {
                "status": "busy", 
                "message": "Orchestrator is already handling a migration. Please wait."
            }
            make_before_break = False # Disable for this request
        else:
            # Example flow for migration
            old_vnf = f"vnf-{placement['name']}".lower()
            new_vnf = f"vnf-{placement['name']}-migrated".lower()
            
            # Helper to manage lock in background
            async def locked_migration():
                async with MIGRATION_LOCK:
                    await container.orchestration_service.make_before_break_sequence(
                        old_name=old_vnf,
                        new_name=new_vnf,
                        file_name="vnf-firewall.yaml" if request.service_type.lower() == "attack" else "vnf-frr.yaml",
                        target_location=_location_key(str(placement["name"])),
                        request=request
                    )

            background_tasks.add_task(locked_migration)
            migration_result = {"status": "triggered", "message": "Make-Before-Break sequence started in background."}

    return {
        "status": "success",
        "placement_node": placement,
        "routing_node": route,
        "srv6_segment_list": sid_stack,
        "method_used": method,
        "hybrid_branch": branch,
        "make_before_break": make_before_break,
        "migration_result": migration_result
    }

@router.post("/orchestrate/migrate-single-vnf")
async def migrate_make(request: MigrateSingleRequest):
    """MAKE phase: Trigger replacement creation."""
    return container.orchestrator.trigger_migrate_single(
        old_deploy_name=request.oldDeployName,
        new_deploy_name=request.newDeployName,
        file_name=request.fileName,
        target_location=request.targetLocation,
        namespace=request.namespace
    )

@router.post("/orchestrate/migrate-single-vnf/break")
async def migrate_break(request: BreakOldVnfRequest):
    """BREAK phase: Delete old VNF after steer verification."""
    if not request.confirm_steer_done:
        raise HTTPException(status_code=400, detail="confirm_steer_done=True is required for BREAK.")
    return container.orchestrator.break_old_vnf(
        old_deploy_name=request.oldDeployName,
        namespace=request.namespace
    )

@router.post("/orchestrate/alert")
async def set_alert(alert: bool):
    """Trigger/Clear forecast alert (Bi-GRU simulation)."""
    get_state_manager().set_forecast_alert(alert)
    return {"status": "success", "alert_flag": alert}

@router.get("/orchestrate/status")
async def get_orchestration_status():
    """
    RÀ SOÁT 4: Bất đồng bộ UI. 
    Frontend gọi endpoint này để biết khi nào Migration thực sự xong.
    """
    is_busy = MIGRATION_LOCK.locked()
    return {
        "status": "success",
        "is_migrating": is_busy,
        "message": "System busy with migration" if is_busy else "System Idle",
        # Hỗ trợ polling cho Tekton Pipeline mới nhất
        "latest_pipeline": container.orchestrator.get_status()
    }
