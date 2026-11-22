from fastapi import APIRouter, HTTPException, BackgroundTasks
import asyncio
import logging
import uuid
import time
from weakref import WeakKeyDictionary

from src.ai.dgrl_agent import get_dgrl_agent
from src.ai.heuristic import HardConstraintError
from src.analytics.ai_forecasting import get_forecast_service
from src.core.state_manager import get_state_manager
from src.portal.backend.app.containers.service_container import container
from src.portal.backend.app.services.hybrid_decision import (
    select_and_reserve,
    node_label,
    location_key,
)
from src.portal.backend.app.services.vnf_service_type import resolve_vnf_service
from src.portal.backend.app.services.controller_topology import fetch_live_p4_topology_hash
from src.portal.backend.app.models.schemas import (
    SFCRequest,
    FreeResourceRequest,
    TelemetryIngestRequest,
)

logger = logging.getLogger("OrchestrationRouter")
router = APIRouter(tags=["Hybrid Orchestration"])

_migration_locks = WeakKeyDictionary()


def get_migration_lock():
    """Create the migration lock in the serving loop, never during import."""
    loop = asyncio.get_running_loop()
    lock = _migration_locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _migration_locks[loop] = lock
    return lock

@router.post("/orchestrate")
async def orchestrate_sfc(request: SFCRequest, background_tasks: BackgroundTasks):
    """
    Adaptive Hybrid Orchestration endpoint.
    """
    state_manager = get_state_manager()
    request_start = time.perf_counter()
    state_sync_start = time.perf_counter()
    try:
        k8s_vnfs = container.orchestrator.list_vnfs()
        state_manager.sync_with_kubernetes(k8s_vnfs)
    except Exception as e:
        logger.error(f"Failed to sync state with K8s during orchestrate: {e}")
    state_sync_ms = (time.perf_counter() - state_sync_start) * 1000.0
    forecaster = get_forecast_service()
    
    # Trigger Forecast Alert if needed
    forecast_decision = None
    forecast_node = request.ingress_node
    if forecast_node is None and isinstance(request.source_node, int):
        forecast_node = request.source_node
    if forecast_node is None:
        forecast_node = 0
    if request.pps is not None:
        forecast_decision = forecaster.observe(int(forecast_node), request.pps)
        state_manager.set_node_forecast_alert(forecast_decision.node_id, forecast_decision.alert)

    forecast_alert = bool(
        request.alert_flag 
        or request.is_ddos_spike 
        or request.service_type.lower() == "attack"
        or (forecast_decision.alert if forecast_decision else False)
    )
    if forecast_alert:
        state_manager.set_forecast_alert(True)

    vnf_name = f"vnf-{request.service_type.lower()}-{str(uuid.uuid4())[:8]}"
    p4_topology_hash = None
    if request.source_node is not None or request.ingress_node is not None:
        controller_url = getattr(
            getattr(container, "orchestration_service", None),
            "sdn_controller_url", "")
        try:
            p4_topology_hash = fetch_live_p4_topology_hash(controller_url)
        except Exception as exc:
            raise HTTPException(status_code=409, detail={
                "status": "error",
                "code": "UNSUPPORTED_ADMITTED_REALIZATION",
                "message": "Live P4 topology and loaded profile could not be verified before admission.",
                "reason": str(exc),
            }) from exc
    try:
        decision = select_and_reserve(
            state_manager, request,
            lambda manager, req: get_dgrl_agent().get_action(manager, req),
            vnf_name=vnf_name,
            p4_topology_hash=p4_topology_hash,
        )
    except HardConstraintError as exc:
        message = str(exc)
        lowered = message.lower()
        if "msd" in lowered:
            reason_key = "msd_violation"
        elif "cpu" in lowered:
            reason_key = "cpu_capacity"
        elif "ram" in lowered:
            reason_key = "ram_capacity"
        elif "telemetry" in lowered:
            reason_key = "stale_telemetry"
        elif "version" in lowered or "stale" in lowered:
            reason_key = "stale_state"
        elif "capacity" in lowered or "full" in lowered:
            reason_key = "placement_capacity"
        else:
            reason_key = "no_safe_action"
        raise HTTPException(
            status_code=409,
            detail={"status": "error", "code": "NO_SAFE_ACTION", "reason_key": reason_key, "message": message},
        ) from exc
    except Exception as exc:
        logger.exception("Orchestration internal error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    choice = decision.choice
    branch = decision.branch
    method = decision.method
    sid_stack = decision.sid_stack
    _, deploy_manifest = resolve_vnf_service(request.service_type)

    public_state = state_manager.as_public_dict()
    node_names = [n["name"] for n in public_state["nodes"]]
    placement = node_label(choice.v_place, node_names)
    route = node_label(choice.v_route, node_names)
    
    # Luồng MBB Proactive nếu có Alert và có VNF đăng ký trong state_manager
    migration_result = None
    controller_handoff_ms = 0.0
    if branch == "drl" and forecast_alert:
        if decision.realization.forwarding_sid is None:
            released, release_reason = state_manager.release_unactuated_reservation(vnf_name)
            raise HTTPException(status_code=409, detail={
                "status": "error",
                "code": "UNSUPPORTED_ADMITTED_REALIZATION",
                "message": "No verified mapping exists from the admitted SID stack to a forwarding profile.",
                "reservation_released": released,
                "reservation_release_reason": release_reason,
            })
        # Mark intent before queuing, so a concurrent TTL cannot release it.
        state_manager.mark_actuation_requested(vnf_name)
        # Tìm VNF cũ tốn CPU nhất trên node được chọn để migrate
        # The reservation for vnf_name was just recorded on this node; it is the
        # replacement being created, never the old instance to migrate from.
        existing_vnfs = [
            vnf for vnf in state_manager.get_vnfs_on_node(choice.v_place)
            if vnf.get("name", "").startswith(
                "vnf-{}-".format(request.service_type.lower()))
            and vnf.get("name") != vnf_name
        ]
        old_vnf = existing_vnfs[0]["name"] if existing_vnfs else None

        if old_vnf:
            handoff_start = time.perf_counter()
            async def background_mbb():
                async with get_migration_lock():
                    await container.orchestration_service.make_before_break_sequence(
                        old_name=old_vnf,
                        new_name=vnf_name,
                        file_name=deploy_manifest,
                        target_location=location_key(str(placement["name"])),
                        request=request,
                        ai_node_id=choice.v_place,
                        admitted_realization=decision.realization,
                    )
            background_tasks.add_task(background_mbb)
            controller_handoff_ms = (time.perf_counter() - handoff_start) * 1000.0
            migration_result = {"status": "triggered", "old_vnf": old_vnf, "new_vnf": vnf_name,
                                "status_path": f"/orchestrate/migrations/{vnf_name}"}
        else:
            handoff_start = time.perf_counter()
            # New service: create, verify its Ready Pod, then install the
            # admitted path. With no matching old service there is no BREAK.
            async def background_deploy_and_steer():
                async with get_migration_lock():
                    await container.orchestration_service.make_before_break_sequence(
                        old_name=None,
                        new_name=vnf_name,
                        file_name=deploy_manifest,
                        target_location=location_key(str(placement["name"])),
                        request=request,
                        ai_node_id=choice.v_place,
                        admitted_realization=decision.realization,
                    )
            background_tasks.add_task(background_deploy_and_steer)
            controller_handoff_ms = (time.perf_counter() - handoff_start) * 1000.0
            migration_result = {
                "status": "creating_and_steering",
                "vnf_name": vnf_name,
                "operation_id": decision.realization.operation_id,
                "status_path": f"/orchestrate/migrations/{vnf_name}",
            }

    timings_ms = {
        "state_sync_ms": state_sync_ms,
        **decision.timings_ms,
        "controller_handoff_ms": controller_handoff_ms,
        "server_decision_ms": (time.perf_counter() - request_start) * 1000.0,
    }

    data = {
        "vnf_name": vnf_name,
        "placement_node": placement,
        "routing_node": route,
        "srv6_segment_list": sid_stack,
        "admitted_realization": {
            "request_id": decision.realization.request_id,
            "operation_id": decision.realization.operation_id,
            "topology_hash": decision.realization.topology_hash,
            "p4_topology_hash": decision.realization.p4_topology_hash,
            "profile_id": decision.realization.profile_id,
            "switch_path": list(decision.realization.switch_path),
            "sid_stack": list(decision.realization.sid_stack),
        },
        "method_used": method,
        "hybrid_branch": branch,
        "decision_state_version": decision.decision_state_version,
        "admission_state_version": decision.admission_state_version,
        "timings_ms": timings_ms,
        "global_utilization": public_state["global_utilization"],
        "avg_cpu": public_state["avg_cpu"],
        "avg_msd_usage": public_state["avg_msd_usage"],
        "alert_flag": public_state["alert_flag"],
        "forecast": {
            "node_id": forecast_decision.node_id,
            "current_pps": forecast_decision.current_pps,
            "predicted_pps": forecast_decision.predicted_pps,
            "alert": forecast_decision.alert,
            "reason": forecast_decision.reason,
        } if forecast_decision else None,
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
        "decision_state_version": decision.decision_state_version,
        "admission_state_version": decision.admission_state_version,
        "timings_ms": timings_ms,
        "migration_result": migration_result
    }

@router.get("/orchestrate/migrations/{replacement}")
def get_migration_status(replacement: str):
    record = container.orchestration_service.get_migration_status(replacement)
    if record is None:
        raise HTTPException(status_code=404, detail="Migration record not found")
    return record


@router.get("/orchestrate/state")
def get_hybrid_state():
    try:
        k8s_vnfs = container.orchestrator.list_vnfs()
        get_state_manager().sync_with_kubernetes(k8s_vnfs)
    except Exception as e:
        logger.error(f"Failed to sync state with K8s in get_hybrid_state: {e}")
    state = get_state_manager().as_public_dict()
    return {
        "status": "success",
        "message": "Hybrid state snapshot",
        "data": state,
        "forecast": get_forecast_service().status(),
    }


@router.post("/orchestrate/telemetry")
def ingest_telemetry(req: TelemetryIngestRequest):
    sm = get_state_manager()
    forecaster = get_forecast_service()
    decisions = []
    for sample in req.samples:
        forecast_alert = sample.alert
        decision = None
        if sample.pps is not None:
            decision = forecaster.observe(sample.node_id, sample.pps)
            forecast_alert = decision.alert
            decisions.append({
                "node_id": decision.node_id,
                "current_pps": decision.current_pps,
                "predicted_pps": decision.predicted_pps,
                "alert": decision.alert,
                "reason": decision.reason,
            })
        sm.update_node_telemetry(
            node_id=sample.node_id,
            cpu_util=sample.cpu_util,
            ram_util=sample.ram_util,
            msd_used=sample.msd_used,
            msd_util=sample.msd_util,
            alert=forecast_alert,
        )
    return {
        "status": "success",
        "message": "Telemetry ingested",
        "forecast": decisions,
        "data": sm.as_public_dict(),
    }

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
                async with get_migration_lock():
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
                                target_location=location_key(target_name),
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
    is_busy = get_migration_lock().locked()
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
    try:
        sm.reset()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"reason_key": str(exc)}) from exc
    state = sm.as_public_dict()
    logger.info("[BENCHMARK] Network state reset by /orchestrate/reset")
    return {
        "status": "success",
        "message": "Network state reset. All resource usage cleared.",
        "data": state
    }

@router.post("/orchestrate/reconcile/{vnf_name}")
async def reconcile_absent_vnf(vnf_name: str):
    """Release a ledger record whose Deployment and Pods are confirmed absent."""
    async with get_migration_lock():
        presence = container.orchestrator.deployment_presence(vnf_name)
        if presence is not False:
            raise HTTPException(status_code=409, detail={
                "code": "ABSENCE_NOT_CONFIRMED", "deployment_presence": presence})
        sm = get_state_manager()
        try:
            sm.sync_with_kubernetes(container.orchestrator.list_vnfs())
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "SYNC_FAILED", "reason": str(exc)}) from exc
        released, reason = sm.release_confirmed_absent(vnf_name)
        if not released:
            raise HTTPException(status_code=409, detail={"code": "RECONCILE_BLOCKED", "reason_key": reason})
        return {"status": "success", "vnf_name": vnf_name, "released": True}


@router.post("/orchestrate/free")
def free_network_resources(req: FreeResourceRequest):
    """
    Giai phong tai nguyen khi SFC het han (TTL expire)
    """
    sm = get_state_manager()
    if req.vnf_name is not None:
        accepted, reason = sm.release_unactuated_reservation(req.vnf_name)
        if not accepted:
            code = ("DEPLOYED_TTL_TEARDOWN_REQUIRED"
                    if reason == "deployed_teardown_required" else "RESERVATION_RELEASE_BLOCKED")
            raise HTTPException(status_code=409, detail={"code": code, "reason_key": reason})
    else:
        sm.free_resources(req.v_place, req.v_route, req.cpu_req, req.ram_req, req.msd_req)
    return {"status": "success", "message": "Resources freed"}
