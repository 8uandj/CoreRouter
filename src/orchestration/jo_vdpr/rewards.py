from typing import List, Dict, Any, Tuple
import numpy as np

class RewardCalculator:
    def __init__(self, 
                 base_reward=100.0, 
                 core_bonus=50.0, 
                 latency_penalty=5.0, 
                 msd_violation=-200.0, 
                 cpu_overflow=-200.0):
        self.BASE_REWARD = base_reward
        self.CORE_BONUS = core_bonus
        self.LATENCY_PENALTY = latency_penalty
        self.MSD_VIOLATION = msd_violation
        self.CPU_OVERFLOW = cpu_overflow

    def calculate(self, 
                  is_valid: bool, 
                  errors: List[str], 
                  is_elephant: bool, 
                  latency: float, 
                  cpu_req: float, 
                  max_cpu: float,
                  node_v1: int,
                  node_v2: int,
                  service_type: str = 'Data') -> float:
        
        if not is_valid:
            penalty = 0.0
            for err in errors:
                if "CPU" in err:
                    penalty += self.CPU_OVERFLOW
                if "MSD" in err:
                    penalty += self.MSD_VIOLATION
            return penalty

        # Valid mapping rewards
        core_bonus = self.CORE_BONUS if is_elephant and (node_v1 == 1 or node_v2 == 1) else 0.0
        resource_efficiency = 1.0 - (cpu_req / max_cpu)
        
        # 1. Tốn thêm processing MS delay khi BSID thay đổi (Detour sang DC khác)
        bsid_processing_delay = 2.0 if node_v1 != node_v2 else 0.0
        effective_latency = latency + bsid_processing_delay

        # 2. Hệ số suy hao dựa trên hạng Traffic
        penalty_multi = 1.0
        if service_type in ['Video', 'VoIP']:
            penalty_multi = 2.0 # Siêu nhạy cảm thời gian
        elif service_type in ['Data', 'IoT']:
            penalty_multi = 0.5 
        elif service_type == 'Attack':
            penalty_multi = 0.1
            
        latency_cost = effective_latency * self.LATENCY_PENALTY * penalty_multi
        
        reward = (self.BASE_REWARD * resource_efficiency) + core_bonus - latency_cost
        return float(reward)
