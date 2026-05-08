from pydantic import BaseModel, Field
from typing import Optional, Union

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
