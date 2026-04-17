from typing import Dict, Any, List
from abc import ABC, abstractmethod

class IOrchestrator(ABC):
    @abstractmethod
    def trigger_deploy(self, name: str, vnf_type: str, profile: str, location: str = "auto") -> Dict[str, Any]:
        """Deploy a VNF instance at a specific location."""
        pass

    @abstractmethod
    def trigger_terminate(self, vnf_name: str) -> Dict[str, Any]:
        """Terminate a deployment."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get the status of deployments."""
        pass

    @abstractmethod
    def list_vnfs(self) -> List[Dict[str, Any]]:
        """List all active VNF instances."""
        pass
