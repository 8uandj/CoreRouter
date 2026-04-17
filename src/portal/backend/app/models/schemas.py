from pydantic import BaseModel
from typing import Optional

class DeployRequest(BaseModel):
    name: str
    type: str    # router, firewall, idps
    profile: str # standard, performance
    location: Optional[str] = "auto"