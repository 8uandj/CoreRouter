from src.infrastructure.k8s.tekton_orchestrator import TektonOrchestrator
from src.infrastructure.sdn.p4_controller import P4Controller
from src.infrastructure.persistence.csv_repository import CSVRepository
from src.portal.backend.app.services.ai_service import AIService
from src.portal.backend.app.services.topology_service import TopologyService
from src.portal.backend.app.services.monitor_service import MonitorService
from src.portal.backend.app.services.orchestration_service import OrchestrationService
from src.portal.backend.app.core.config import settings
from src.portal.backend.app.services.migration_journal import MigrationJournal
import os
from src.core.state_manager import get_state_manager

class ServiceContainer:
    def __init__(self):
        # Restore admission charges before exposing integrations or accepting work.
        get_state_manager().enable_persistence(os.getenv(
            "CORE_ROUTER_RESERVATION_DB", "results/rev1/runtime/reservations.sqlite3"))
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
            settings.SDN_CONTROLLER_URL,
            state_manager=get_state_manager(),
            migration_journal=MigrationJournal(os.getenv(
                "CORE_ROUTER_MIGRATION_JOURNAL", "results/rev1/runtime/migrations.sqlite3")),
        )

# Singleton instance
container = ServiceContainer()
