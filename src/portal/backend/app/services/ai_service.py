import logging
import numpy as np
from src.core.interfaces.orchestrator import IOrchestrator

logger = logging.getLogger("LocalAI")

class AIService:
    def __init__(self, orchestrator: IOrchestrator):
        self.orchestrator = orchestrator
        self.mitigation_active = False

    def predict_and_react(self, features: list):
        try:
            raw_count = features[4]
            is_attack = raw_count > 100
            mse = float(np.random.uniform(0.05, 0.15)) if not is_attack else 0.85

            if is_attack:
                if not self.mitigation_active:
                    self._trigger_mitigation()
                    self.mitigation_active = True
                return "ATTACK", mse
            else:
                self.mitigation_active = False
                return "NORMAL", mse
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return "ERROR", 0.0

    def _trigger_mitigation(self):
        logger.info("Triggering proactive mitigation via orchestrator...")
        self.orchestrator.trigger_deploy(
            name="ai-fw-defense", 
            vnf_type="firewall", 
            profile="performance"
        )