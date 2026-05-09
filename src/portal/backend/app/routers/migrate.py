"""Phase 2.2 backend contract for single-VNF Make-Before-Break migration.

Workflow:
    MAKE   -> POST /api/orchestrate/migrate-single-vnf
    VERIFY -> GET  /api/orchestrate/migrate-single-vnf/status?run=<runName>
              GET  /api/orchestrate/migrate-single-vnf/endpoint?deploy=<newDeployName>
    STEER  -> handled by SDN/P4 controller (out of scope here)
    BREAK  -> POST /api/orchestrate/migrate-single-vnf/break  (explicit only)

The endpoints intentionally never auto-delete the old VNF: BREAK is gated by
``confirm_steer_done=true`` so traffic is not lost if steer is not yet wired.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import logging

from src.portal.backend.app.containers.service_container import container
from src.portal.backend.app.models.schemas import (
    BreakOldVnfRequest,
    MigrateSingleRequest,
)

logger = logging.getLogger("MigrateRouter")
router = APIRouter(tags=["VNF Migration (Make-Before-Break)"])


@router.post("/orchestrate/migrate-single-vnf")
def migrate_single_vnf(request: MigrateSingleRequest):
    """MAKE only. Creates the replacement VNF; old VNF stays alive."""
    result = container.orchestrator.trigger_migrate_single(
        old_deploy_name=request.oldDeployName,
        new_deploy_name=request.newDeployName,
        file_name=request.fileName,
        target_location=request.targetLocation,
        namespace=request.namespace,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result)
    return {
        "status": "success",
        "message": result.get("message", "Migration MAKE pipeline started."),
        "data": result,
    }


@router.get("/orchestrate/migrate-single-vnf/status")
def migrate_single_vnf_status(
    run: str = Query(..., description="PipelineRun name returned by MAKE"),
    namespace: str = Query("core-router"),
):
    result = container.orchestrator.get_pipelinerun_status(run_name=run, namespace=namespace)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result)
    return {"status": "success", "message": "PipelineRun status", "data": result}


@router.get("/orchestrate/migrate-single-vnf/endpoint")
def migrate_single_vnf_endpoint(
    deploy: str = Query(..., description="Replacement deployment name"),
    namespace: str = Query("core-router"),
    service: Optional[str] = Query(None, description="Override service name (defaults to <deploy>-svc)"),
):
    result = container.orchestrator.get_replacement_endpoint(
        deploy_name=deploy, namespace=namespace, service_name=service,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result)
    return {"status": "success", "message": "Replacement endpoint", "data": result}


@router.post("/orchestrate/migrate-single-vnf/break")
def migrate_single_vnf_break(request: BreakOldVnfRequest):
    """Explicit BREAK. Refuses to run unless caller asserts steer success."""
    if not request.confirm_steer_done:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "code": "STEER_NOT_CONFIRMED",
                "message": (
                    "Refusing to delete old VNF: confirm_steer_done=false. "
                    "Verify SDN traffic switch first, then retry with confirm_steer_done=true."
                ),
            },
        )
    result = container.orchestrator.break_old_vnf(
        old_deploy_name=request.oldDeployName, namespace=request.namespace,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result)
    return {"status": "success", "message": result.get("message"), "data": result}
