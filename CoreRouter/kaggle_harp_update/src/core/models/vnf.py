from dataclasses import dataclass
from typing import Optional

@dataclass
class VNFRequest:
    name: str
    type: str
    profile: str = "standard"
    cpu_req: float = 0.0
    ram_req: float = 0.0
    msd_req: int = 0
    is_ddos: bool = False

@dataclass
class SFCFlow:
    v1_node: int
    v2_node: int
    latency: float
    is_elephant: bool
