from fastapi import APIRouter, HTTPException, BackgroundTasks
import asyncio
import logging
from typing import Dict, List, Optional

from src.ai.dgrl_agent import get_dgrl_agent
from src.ai.heuristic import HardConstraintError, get_decoupled_action
from src.core.state_manager import get_state_manager
from src.portal.backend.app.containers.service_container import container
from src.portal.backend.app.models.schemas import SFCRequest, MigrateSingleRequest, BreakOldVnfRequest, FreeResourceRequest

logger = logging.getLogger("OrchestrationRouter")
router = APIRouter(tags=["Hybrid Orchestration"])

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
    """
    Map AI topology node name -> targetLocation label used by Tekton prepare-vnf task.
    Format: "<city>-<index>" matches core-router/location label in K8s manifests.
    Nodes sharing the same physical K8s host get the same location label.
      k8s-master  : Hanoi, HaiPhong, NinhBinh  → hanoi-1
      worker1     : Vinh, Hue, DaNang          → danang-1
      worker2     : QuyNhon, NhaTrang, HoChiMinh, CanTho → hcm-1
    """
    mapping = {
        "Hanoi":      "hanoi-1",
        "HaiPhong":   "hanoi-1",   # same k8s-master cluster
        "NinhBinh":   "hanoi-1",   # same k8s-master cluster
        "Vinh":       "danang-1",
        "Hue":        "danang-1",
        "DaNang":     "danang-1",
        "QuyNhon":    "hcm-1",
        "NhaTrang":   "hcm-1",
        "HoChiMinh":  "hcm-1",
        "CanTho":     "hcm-1",
    }
    return mapping.get(node_name, "auto")


@router.post("/orchestrate")
async def orchestrate_sfc(request: SFCRequest, background_tasks: BackgroundTasks):
    """
    Adaptive Hybrid Orchestration endpoint.
    """
    state_manager = get_state_manager()
    
    # Trigger Forecast Alert if needed
    forecast_alert = bool(
        request.alert_flag 
        or request.is_ddos_spike 
        or request.service_type.lower() == "attack"
    )
    if forecast_alert:
        state_manager.set_forecast_alert(True)

    gate = state_manager.choose_mode()
    method = "Hybrid:Heuristic"
    branch = "heuristic"

    try:
        if gate.mode == "heuristic":
            try:
                choice = get_decoupled_action(state_manager.snapshot(), request)
            except HardConstraintError:
                dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
                choice = dgrl_decision.choice
                branch = "drl"
                method = "Hybrid:DRL (Heuristic Fallback)"
        else:
            dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
            choice = dgrl_decision.choice
            branch = "drl"
            method = "Hybrid:DRL"

        sid_stack = _generate_srv6_sids(choice.v_place, choice.v_route, request.msd_req)
        
        # Phase 7: Generate unique VNF name for tracking
        import uuid
        vnf_id = str(uuid.uuid4())[:8]
        vnf_name = f"vnf-{request.service_type.lower()}-{vnf_id}"

        # Admission Control with Tracking
        accepted, error = state_manager.try_reserve(
            choice.v_place, choice.v_route, request.cpu_req, request.ram_req, len(sid_stack),
            vnf_name=vnf_name
        )

        if not accepted and branch == "heuristic":
            dgrl_decision = get_dgrl_agent().get_action(state_manager, request)
            choice = dgrl_decision.choice
            sid_stack = _generate_srv6_sids(choice.v_place, choice.v_route, request.msd_req)
            accepted, error = state_manager.try_reserve(
                choice.v_place, choice.v_route, request.cpu_req, request.ram_req, len(sid_stack),
                vnf_name=vnf_name
            )
            if accepted:
                branch = "drl"
                method = "Hybrid:DRL (Capacity Fallback)"

        if not accepted:
            raise HTTPException(
                status_code=409,
                detail={"status": "error", "code": "NO_SAFE_ACTION", "message": error or "Hardware constraints violated."}
            )

    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Orchestration internal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    public_state = state_manager.as_public_dict()
    node_names = [n["name"] for n in public_state["nodes"]]
    placement = _node_label(choice.v_place, node_names)
    route = _node_label(choice.v_route, node_names)
    
    # Luồng MBB Proactive nếu có Alert và có VNF đăng ký trong state_manager
    migration_result = None
    if branch == "drl" and forecast_alert:
        # Tìm VNF cũ tốn CPU nhất trên node được chọn để migrate
        existing_vnfs = state_manager.get_vnfs_on_node(choice.v_place)
        old_vnf = existing_vnfs[0]["name"] if existing_vnfs else None

        if old_vnf:
            async def background_mbb():
                async with MIGRATION_LOCK:
                    await container.orchestration_service.make_before_break_sequence(
                        old_name=old_vnf,
                        new_name=vnf_name,
                        file_name="vnf-firewall.yaml" if request.service_type.lower() == "attack" else "vnf-frr.yaml",
                        target_location=_location_key(str(placement["name"])),
                        request=request,
                        ai_node_id=choice.v_place
                    )
            background_tasks.add_task(background_mbb)
            migration_result = {"status": "triggered", "old_vnf": old_vnf, "new_vnf": vnf_name}
        else:
            # Không có VNF cũ → chỉ deploy VNF mới thông thường qua Tekton
            async def background_deploy():
                container.orchestrator.trigger_deploy(
                    name=vnf_name,
                    vnf_type="router",
                    profile="standard",
                    location=_location_key(str(placement["name"]))
                )
            background_tasks.add_task(background_deploy)
            migration_result = {"status": "deploying", "vnf_name": vnf_name}

    data = {
        "vnf_name": vnf_name,
        "placement_node": placement,
        "routing_node": route,
        "srv6_segment_list": sid_stack,
        "method_used": method,
        "hybrid_branch": branch,
        "global_utilization": public_state["global_utilization"],
        "avg_cpu": public_state["avg_cpu"],
        "avg_msd_usage": public_state["avg_msd_usage"],
        "alert_flag": public_state["alert_flag"],
        "migration_result": migration_result,
        "state": public_state,
    }

    return {
        "status": "success",
        "message": f"Hybrid orchestration selected {method}.",
        "data": data,
        # Compatibility: keep the flat response shape used by benchmark scripts.
        "vnf_name": vnf_name,
        "placement_node": placement,
        "routing_node": route,
        "srv6_segment_list": sid_stack,
        "method_used": method,
        "hybrid_branch": branch,
        "migration_result": migration_result
    }

@router.get("/orchestrate/state")
def get_hybrid_state():
    state = get_state_manager().as_public_dict()
    return {"status": "success", "message": "Hybrid state snapshot", "data": state}

@router.post("/orchestrate/alert")
async def set_alert(alert: bool, background_tasks: BackgroundTasks):
    """
    SOTA PROACTIVE MIGRATION: Triggered by Bi-GRU.
    Avoids 'Migration Storm' via Rate-limited Sequential Execution.
    """
    sm = get_state_manager()
    sm.set_forecast_alert(alert)
    
    if alert:
        snap = sm.snapshot()
        # Tìm node bị "sốt" (CPU > 80%)
        hot_nodes = [n["id"] for n in snap.nodes if n["cpu_util"] > 80.0]
        
        if hot_nodes:
            logger.info(f"PHASE 7 ALERT: Hot nodes {hot_nodes}. Sequential migration starting...")
            
            async def sequential_proactive_migration():
                async with MIGRATION_LOCK:
                    for node_id in hot_nodes:
                        vnfs = sm.get_vnfs_on_node(node_id)
                        # Sắp xếp ngốn CPU giảm dần
                        vnfs.sort(key=lambda x: x["cpu_req"], reverse=True)
                        
                        for vnf in vnfs:
                            logger.info(f"PHASE 7 PROACTIVE: Migrating {vnf['name']} (CPU {vnf['cpu_req']})")
                            
                            from src.portal.backend.app.models.schemas import SFCRequest
                            fake_req = SFCRequest(
                                cpu_req=vnf["cpu_req"], ram_req=vnf["ram_req"], msd_req=vnf["msd_req"],
                                service_type="Video"
                            )
                            
                            dgrl_decision = get_dgrl_agent().get_action(sm, fake_req)
                            target_node_id = dgrl_decision.choice.v_place
                            target_name = snap.node_names[target_node_id]
                            
                            # MBB TUẦN TỰ - Đợi xong mới làm tiếp
                            await container.orchestration_service.make_before_break_sequence(
                                old_name=vnf["name"],
                                new_name=f"{vnf['name']}-mig",
                                file_name="vnf-frr.yaml",
                                target_location=_location_key(target_name),
                                request=fake_req,
                                ai_node_id=target_node_id
                            )
            
            background_tasks.add_task(sequential_proactive_migration)
            return {"status": "triggered", "message": f"Sequential proactive migration started for {len(hot_nodes)} nodes."}

    return {"status": "success", "alert_flag": alert}

@router.get("/orchestrate/status")
async def get_orchestration_status():
    """
    RÀ SOÁT 4: Bất đồng bộ UI. 
    """
    is_busy = MIGRATION_LOCK.locked()
    return {
        "status": "success",
        "is_migrating": is_busy,
        "message": "System busy with migration" if is_busy else "System Idle",
        "latest_pipeline": container.orchestrator.get_status()
    }


@router.post("/orchestrate/reset")
def reset_network_state():
    """
    Reset toan bo network state (CPU/RAM/MSD usage) ve 0.
    Dung truoc khi chay benchmark de clear ghost SFCs tu cac lan test truoc.
    CANH BAO: Chi dung cho Benchmark/Testing, KHONG dung trong Production.
    """
    sm = get_state_manager()
    sm.reset()
    state = sm.as_public_dict()
    logger.info("[BENCHMARK] Network state reset by /orchestrate/reset")
    return {
        "status": "success",
        "message": "Network state reset. All resource usage cleared.",
        "data": state
    }

@router.post("/orchestrate/free")
def free_network_resources(req: FreeResourceRequest):
    """
    Giai phong tai nguyen khi SFC het han (TTL expire)
    """
    sm = get_state_manager()
    sm.free_resources(req.v_place, req.v_route, req.cpu_req, req.ram_req, req.msd_req)
    return {"status": "success", "message": "Resources freed"}
