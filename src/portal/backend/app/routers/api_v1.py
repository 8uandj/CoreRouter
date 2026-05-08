from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.portal.backend.app.containers.service_container import container
from src.portal.backend.app.models.schemas import DeployRequest

router = APIRouter()

class P4RuleRequest(BaseModel):
    target_mac: str
    srv6_sid: str
    egress_port: int

@router.get("/health")
def health():
    return {"status": "online", "system": "3S-COM Orchestrator PRO"}

@router.get("/vnfs")
def get_vnfs():
    return container.topology_service.get_topology()

@router.post("/deploy")
def deploy_vnf(request: DeployRequest):
    return container.orchestrator.trigger_deploy(
        name=request.name, 
        vnf_type=request.type, 
        profile=request.profile,
        location=request.location
    )

@router.get("/pipelineruns/latest")
def get_progress():
    return container.orchestrator.get_status()

@router.delete("/vnfs/{vnf_name}")
def terminate_vnf(vnf_name: str):
    return container.orchestrator.trigger_terminate(vnf_name)

@router.get("/metrics/router")
def get_metrics():
    return container.monitor_service.get_metrics()

@router.post("/p4/rules")
def add_p4_rule(request: P4RuleRequest):
    success = container.controller.inject_sfc_rule(
        target_mac=request.target_mac, 
        srv6_sid=request.srv6_sid, 
        egress_port=request.egress_port
    )
    
    if success:
        return {"status": "success", "message": "P4 rule injected successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to inject P4 rule.")    