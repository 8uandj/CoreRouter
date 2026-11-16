from pydantic import BaseModel, Field
from typing import List, Optional, Union

class DeployRequest(BaseModel):
    name: str
    type: str    # router, firewall, idps
    profile: str # standard, performance
    location: Optional[str] = "auto"


class SFCRequest(BaseModel):
    flow_id: Optional[str] = None
    cpu_req: float = Field(default=10.0, ge=0.0, le=100.0)
    ram_req: float = Field(default=5.0, ge=0.0, le=100.0)
    msd_req: int = Field(default=2, ge=1, le=10)
    service_type: str = "Data"
    is_ddos_spike: bool = False
    alert_flag: bool = False
    source_node: Optional[Union[int, str]] = None
    destination_node: Optional[Union[int, str]] = None
    ingress_node: Optional[int] = Field(default=None, ge=0)
    pps: Optional[float] = Field(default=None, ge=0.0, description="Observed or estimated packets per second for forecasting.")


class MigrateSingleRequest(BaseModel):
    """Phase 2.2 — MAKE step of single-VNF Make-Before-Break migration.

    The endpoint only triggers replacement creation. Traffic steering and
    deletion of the old VNF are handled separately so the controller can
    verify the new path before committing to BREAK.
    """
    oldDeployName: str = Field(..., description="Existing VNF deployment to be replaced")
    newDeployName: str = Field(..., description="Target name for replacement deployment")
    fileName: str = Field(default="vnf-frr.yaml", description="Manifest key in vnf-inputs ConfigMap")
    targetLocation: str = Field(default="auto", description="Target location label (hn/dn/hcm/auto)")
    namespace: str = Field(default="core-router")


class BreakOldVnfRequest(BaseModel):
    """Phase 2.2 — BREAK step. Only call AFTER controller has switched traffic."""
    oldDeployName: str
    namespace: str = Field(default="core-router")
    confirm_steer_done: bool = Field(
        default=False,
        description="Caller must explicitly assert SDN steer succeeded before BREAK.",
    )

class FreeResourceRequest(BaseModel):
    v_place: int
    v_route: int
    cpu_req: float
    ram_req: float
    msd_req: int


class TelemetryNodeSample(BaseModel):
    node_id: int = Field(..., ge=0)
    cpu_util: Optional[float] = Field(default=None, ge=0.0)
    ram_util: Optional[float] = Field(default=None, ge=0.0)
    msd_used: Optional[float] = Field(default=None, ge=0.0)
    msd_util: Optional[float] = Field(default=None, ge=0.0)
    pps: Optional[float] = Field(default=None, ge=0.0)
    alert: Optional[bool] = None


class TelemetryIngestRequest(BaseModel):
    samples: List[TelemetryNodeSample]
