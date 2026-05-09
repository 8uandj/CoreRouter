from abc import ABC, abstractmethod
from typing import Optional

class IController(ABC):
    @abstractmethod
    def inject_sfc_rule(self, target_mac: str, srv6_sid: str, egress_port: int) -> bool:
        """Inject an SFC rule into the SDN data plane."""
        pass

    @abstractmethod
    def get_topology(self) -> dict:
        """Retrieve the current network topology."""
        pass
