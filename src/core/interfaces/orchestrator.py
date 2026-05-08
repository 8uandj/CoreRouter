from typing import Dict, Any, List, Optional
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

    # --- Phase 2.2: Make-Before-Break single-VNF migration -------------------
    def trigger_migrate_single(
        self,
        old_deploy_name: str,
        new_deploy_name: str,
        file_name: str,
        target_location: str = "auto",
        namespace: str = "core-router",
    ) -> Dict[str, Any]:
        """Start a Make-only PipelineRun that creates a replacement VNF.

        Implementations MUST NOT delete the old VNF and MUST NOT steer traffic.
        Returns metadata about the created PipelineRun.
        """
        raise NotImplementedError

    def get_pipelinerun_status(self, run_name: str, namespace: str = "core-router") -> Dict[str, Any]:
        """Return condition/reason for a specific PipelineRun by name."""
        raise NotImplementedError

    def get_replacement_endpoint(
        self,
        deploy_name: str,
        namespace: str = "core-router",
        service_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return readiness + NodePort/clusterIP info for the replacement deployment."""
        raise NotImplementedError

    def break_old_vnf(self, old_deploy_name: str, namespace: str = "core-router") -> Dict[str, Any]:
        """Deferred BREAK hook. Only call AFTER controller has switched traffic."""
        raise NotImplementedError
