"""
rewards.py — JO-VDPR Reward Calculator v4 (Phase 8 — MaskablePPO)

Nâng cấp từ Phase 7 (v3):
    [NEW]  Proportional Knapsack Reward:
           Khi Agent map thành công một SFC, phần thưởng không còn cố định mà tỷ lệ
           thuận với (msd_req × cpu_req) nhân hệ số knapsack_scale để chuẩn hoá.
           Tư duy: SFC 'nặng' và 'dài' có giá trị cao hơn → Agent tự học ưu tiên
           nét đồ thị tối ưu (Elephant → Core DC, Mouse → Edge DC).
    [KEEP] MSD Violation penalty được điều chỉnh bởi AdaptivePenaltyCallback (λ_msd).
    [KEEP] Switching cost, Load Balance Bonus, Core DC Bonus.
    [KEEP] Traffic-aware latency penalty.
"""

from typing import List


class RewardCalculator:
    # Các node Core DC theo topology Phase 7
    CORE_NODES = frozenset({0, 1, 5, 8})   # Hanoi, HaiPhong, DaNang, HoChiMinh

    def __init__(self,
                 base_reward:     float = 100.0,
                 core_bonus:      float = 30.0,
                 latency_penalty: float = 1.0,      # Hệ số scale trễ gốc
                 lambda_latency:   float = -10.0,    # Adaptive Penalty cho vi phạm SLA
                 cpu_overflow:    float = -20.0,
                 balance_bonus:   float = 15.0,
                 switching_cost:  float = -10.0,
                 knapsack_scale:  float = 0.5):
        """
        knapsack_scale: Hệ số chuẩn hoá cho Proportional Knapsack Reward.
            Phần thưởng knapsack = knapsack_scale * (msd_req * cpu_req).
            Cần điều chỉnh để knapsack_bonus không vượt quá 10~20%% giá trị BASE_REWARD.
            Mặc định 0.5: với msd_req~3, cpu_req~20 → bonus = 0.5*60 = 30 (được).
            Giá chị 1.0 sẽ làm scale reward không đồng nhất, nhiễu gradient PPO.
        """
        self.BASE_REWARD     = base_reward
        self.CORE_BONUS      = core_bonus
        self.LATENCY_PENALTY = latency_penalty
        self.lambda_latency  = lambda_latency   # Mutable, cập nhật bởi AdaptivePenaltyCallback
        self.CPU_OVERFLOW    = cpu_overflow
        self.BALANCE_BONUS   = balance_bonus
        self.SWITCHING_COST  = switching_cost
        self.KNAPSACK_SCALE  = knapsack_scale
        
        # Ngưỡng SLA trễ vật lý (Vietnam Backbone aware)
        self.LATENCY_THRESHOLDS = {
            'IoT':   15.0,   # URLLC / Critical IoT
            'Video': 30.0,   # eMBB
            'VoIP':  50.0,   # Voice (ITU-T G.114 aware)
            'Data':  100.0,  # Best-effort
            'Attack': 500.0  # Lowest priority
        }

    # ─────────────────────────────────────────────────────────────
    #  API để AdaptivePenaltyCallback điều chỉnh λ
    # ─────────────────────────────────────────────────────────────
    def update_lambda_latency(self, new_lambda: float) -> None:
        """Được gọi bởi AdaptivePenaltyCallback."""
        self.lambda_latency = float(new_lambda)

    def calculate(self,
                  is_valid:     bool,
                  errors:       List[str],
                  is_elephant:  bool,
                  latency:      float,
                  cpu_req:      float,
                  msd_req:      int,         # [NEW] cần thiết cho Knapsack Reward
                  max_cpu:      float,
                  node_v1:      int,
                  node_v2:      int,
                  service_type: str  = 'Data',
                  is_switching: bool = False) -> float:

        # ── Hardware Constraints (Handled by Action Masking) ──
        # Trả về phạt nhẹ làm backup, thực tế MaskablePPO sẽ không bao giờ chọn nhầm.
        if not is_valid:
            return float(self.CPU_OVERFLOW)

        # ── Resource Efficiency ──────────────────────────────────
        resource_eff = 1.0 - (cpu_req / max_cpu)

        # ── Bonuses ──────────────────────────────────────────────
        # Load Balance: thưởng khi traffic phân tán qua 2 node khác nhau
        balance  = self.BALANCE_BONUS if node_v1 != node_v2 else 0.0
        # Core DC: thưởng elephant flows đi qua Core
        core_b   = self.CORE_BONUS if (
            is_elephant and (node_v1 in self.CORE_NODES or node_v2 in self.CORE_NODES)
        ) else 0.0
        # Switching: phạt khi thay đổi DC assignment (cập nhật FIB)
        switch_c = self.SWITCHING_COST if is_switching else 0.0

        # ── Latency Cost (total = propagation + processing) ──────
        penalty_multi = {
            'Video': 3.0, 'VoIP': 3.0,   # SLA khắt khe (< 100ms)
            'Data':  0.5, 'IoT': 0.5,    # Best-effort
            'Attack': 0.05               # Không cần tối ưu speed
        }.get(service_type, 1.0)

        # ── Latency Cost (tổng quan) ─────────────────────────────
        # penalty_multi đã được tính ở trên dựa trên service_type
        latency_cost = latency * self.LATENCY_PENALTY * penalty_multi

        # ── [NEW] SLA Latency Adaptive Penalty ────────────────────
        threshold = self.LATENCY_THRESHOLDS.get(service_type, 100.0)
        violation_penalty = 0.0
        if latency > threshold:
            # Phạt λ tỷ lệ với mức độ vượt ngưỡng để làm mượt bề mặt loss
            violation_penalty = self.lambda_latency * (latency / threshold)

        # ── [NEW] Proportional Knapsack Bonus ───────────────────────
        knapsack_bonus = self.KNAPSACK_SCALE * (msd_req * cpu_req)

        reward = (self.BASE_REWARD * resource_eff) + knapsack_bonus + core_b + balance + switch_c - latency_cost + violation_penalty
        return float(reward)
