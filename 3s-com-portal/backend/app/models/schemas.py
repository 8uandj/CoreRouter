from pydantic import BaseModel

class DeployRequest(BaseModel):
    name: str
    type: str    # router, firewall, idps
    profile: str # standard, performance