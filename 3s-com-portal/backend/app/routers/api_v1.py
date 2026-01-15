from fastapi import APIRouter
from app.models.schemas import DeployRequest
from app.services import topology_service, tekton_service, monitor_service

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "online", "system": "3S-COM Orchestrator PRO"}

@router.get("/vnfs")
def get_vnfs():
    return topology_service.get_topology()

@router.post("/deploy")
def deploy_vnf(request: DeployRequest):
    return tekton_service.trigger_deploy(request)

@router.get("/pipelineruns/latest")
def get_progress():
    return tekton_service.get_pipeline_status()

@router.get("/metrics/router")
def get_metrics():
    return monitor_service.get_metrics()