from src.infrastructure.k8s.tekton_orchestrator import TektonOrchestrator
from src.infrastructure.sdn.p4_controller import P4Controller
from src.infrastructure.persistence.csv_repository import CSVRepository
from src.portal.backend.app.services.ai_service import AIService
from src.portal.backend.app.services.topology_service import TopologyService
from src.portal.backend.app.services.monitor_service import MonitorService
from src.portal.backend.app.services.orchestration_service import OrchestrationService
from src.portal.backend.app.core.config import settings

class ServiceContainer:
    def __init__(self):
        # Infrastructure
        self.orchestrator = TektonOrchestrator()
        self.controller = P4Controller()
        self.repository = CSVRepository()

        # Services
        self.ai_service = AIService(self.orchestrator)
        self.topology_service = TopologyService(self.orchestrator)
        self.monitor_service = MonitorService(settings.PROMETHEUS_URL)
        self.orchestration_service = OrchestrationService(
            self.orchestrator, 
            self.controller, 
            settings.SDN_CONTROLLER_URL
        )

# Singleton instance
container = ServiceContainer()
