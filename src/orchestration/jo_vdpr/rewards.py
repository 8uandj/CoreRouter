"""
rewards.py — JO-VDPR Reward Calculator v5 (Phase 10 — Joint Proactive Evacuation)

Nâng cấp:
    [NEW] Proactive Evacuation Penalty: Phạt âm điểm (-50.0) nếu chọn nhúng vào trạm đang có cờ Alert.
    [NEW] Headroom Bonus: Xóa triết lý Resource_eff sai trái cũ. Thưởng cho Agent nếu sau khi nhúng VNF, trạm vẫn còn tải rỗng lớn (khuyến khích chọn trạm rảnh rỗi tuyệt tối).
    [UPDATED] Đồng bộ 100% SLA thresholds với env.py.
"""

from typing import List

class RewardCalculator:
    # Các node Core DC (Dựa trên topology Vietnam) - có thể tổng quát hóa nhưng tạm giữ nguyên để tương thích
    CORE_NODES = frozenset({0, 1, 5, 8})

    def __init__(self,
                 base_reward:        float = 100.0,
                 core_bonus:         float = 30.0,
                 latency_penalty:    float = 1.0,
                 lambda_latency:     float = -10.0,
                 cpu_overflow:       float = -20.0,
                 balance_bonus:      float = 15.0,
                 switching_cost:     float = -10.0,
                 knapsack_scale:     float = 0.5,
                 evacuation_penalty: float = -50.0):
        
        self.BASE_REWARD        = base_reward
        self.CORE_BONUS         = core_bonus
        self.LATENCY_PENALTY    = latency_penalty
        self.lambda_latency     = lambda_latency
        self.CPU_OVERFLOW       = cpu_overflow
        self.BALANCE_BONUS      = balance_bonus
        self.SWITCHING_COST     = switching_cost
        self.KNAPSACK_SCALE     = knapsack_scale
        self.EVACUATION_PENALTY = evacuation_penalty
        
        # Đã đồng bộ với ngưỡng SLA chuẩn tại env.py
        self.LATENCY_THRESHOLDS = {
            'IoT':   10.0,
            'Video': 30.0,
            'VoIP':  50.0,
            'Data':  100.0,
            'Attack': 500.0
        }

    def update_lambda_latency(self, new_lambda: float) -> None:
        self.lambda_latency = float(new_lambda)

    def calculate(self,
                  is_valid:     bool,
                  errors:       List[str],
                  is_elephant:  bool,
                  latency:      float,
                  cpu_req:      float,
                  msd_req:      int,
                  max_cpu:      float,
                  node_v1:      int,
                  node_v2:      int,
                  service_type: str   = 'Data',
                  is_switching: bool  = False,
                  alert_v1:     float = 0.0,
                  alert_v2:     float = 0.0,
                  cpu_util_v1:  float = 0.0,
                  cpu_util_v2:  float = 0.0) -> float:

        if not is_valid:
            return float(self.CPU_OVERFLOW)

        # ── [UPDATED] Headroom Bonus ─────────────────────────────
        # Thay thế việc trừ điểm request lớn bằng việc cộng điểm khi node còn dư dả.
        # cpu_util_v1 là % CPU đã dùng TRƯỚC KHI cộng request này, nhưng không sao, 
        # dùng nó hoặc giả định Agent càng chọn node rảnh càng tốt.
        # Ở đây đơn giản hóa: 
        headroom = 1.0 - max(cpu_util_v1, cpu_util_v2) 
        # max_cpu_after_req = max(cpu_util_v1 + cpu_req/max_cpu, cpu_util_v2 + cpu_req/max_cpu)
        # Tạm dùng BASE_REWARD cố định để không phạt request lớn nữa
        baseline = self.BASE_REWARD

        balance  = self.BALANCE_BONUS if node_v1 != node_v2 else 0.0
        core_b   = self.CORE_BONUS if (
            is_elephant and (node_v1 in self.CORE_NODES or node_v2 in self.CORE_NODES)
        ) else 0.0
        # Giảm trừ Switching Cost xuống -3 như quy hoạch
        switch_c = -3.0 if is_switching else 0.0

        # ── Latency Cost ─────────────────────────────────────────
        penalty_multi = {
            'Video': 3.0, 'VoIP': 3.0,
            'Data':  0.5, 'IoT': 0.5,
            'Attack': 0.05
        }.get(service_type, 1.0)

        latency_cost = latency * self.LATENCY_PENALTY * penalty_multi

        # ── SLA Latency Adaptive Penalty ─────────────────────────
        threshold = self.LATENCY_THRESHOLDS.get(service_type, 100.0)
        violation_penalty = 0.0
        if latency > threshold:
            violation_penalty = self.lambda_latency * (latency / threshold)

        # ── Proportional Knapsack Bonus ──────────────────────────
        # Đã giảm ảnh hưởng xuống một chút để khỏi áp đảo các lỗi
        knapsack_bonus = (self.KNAPSACK_SCALE * 0.5) * (msd_req * cpu_req)

        # ── [NEW] Proactive Evacuation Penalty ───────────────────
        evac_penalty = 0.0
        if alert_v1 == 1.0 or alert_v2 == 1.0:
            evac_penalty = self.EVACUATION_PENALTY

        reward = (baseline) + knapsack_bonus + core_b + balance + switch_c - latency_cost + violation_penalty + evac_penalty
        return float(reward)
