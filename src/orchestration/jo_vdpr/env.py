"""
env.py — JO-VDPR RL Environment v4 (Phase 8 — MaskablePPO)

Nâng cấp từ Phase 7 (v3):
    [NEW]  action_masks(): Hỗ trợ Invalid Action Masking cho sb3-contrib MaskablePPO.
           Trả về boolean array (2 × num_nodes,) để loại bỏ các node đã cạn kiệt CPU
           hoặc MSD khỏi không gian hành động ngay trước Softmax của Actor.
           → Agent tập trung 100%% exploration vào các node còn khả dụng.
    [KEEP] Processing latency: độ trễ tại switch tăng tuyến tính theo MSD_used.
    [KEEP] Switching cost: nếu Agent thay đổi DC assignment so với bước trước,
           env báo flag để RewardCalculator trừ chi phí cập nhật FIB/SRv6 policy.
    [KEEP] Violation tracking: mã hoá tỷ lệ vi phạm trong 20 bước gần nhất vào info{}
           để AdaptivePenaltyCallback điều chỉnh λ_msd.

Observation (48 dims):
    [0..39]  : 10 × 4 node features [cpu, ram, msd_used, msd_free]
    [40..42] : request [cpu_req, ram_req, msd_req]
    [43..47] : traffic class one-hot
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from collections import deque

from src.core.interfaces.repository import IRepository
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import (
    LATENCY_MATRIX, MSD_LIMITS, NUM_NODES, NAMES
)

# Hệ số độ trễ xử lý tại switch: mỗi slot MSD bị chiếm dụng ~ 0.3ms thêm
PROC_COEF_MS = 0.3


class JOVDPREnv(gym.Env):

    NODE_FEAT_DIM = 4   # cpu_used, ram_used, msd_used, msd_free
    REQ_FEAT_DIM  = 3   # cpu_req, ram_req, msd_req
    TRAFFIC_DIM   = 5   # Video, VoIP, Data, IoT, Attack

    # Ngưỡng SLA trễ (Vietnam Backbone aware — Đồng bộ với rewards.py)
    LATENCY_THRESHOLDS = {
        'IoT':   15.0, 'Video': 30.0, 'VoIP': 50.0, 'Data': 100.0, 'Attack': 500.0
    }

    def __init__(self,
                 repository: IRepository,
                 reward_calculator: RewardCalculator | None = None,
                 num_nodes: int = NUM_NODES,
                 episode_length: int = 100):
        super().__init__()
        self.num_nodes   = num_nodes
        self.repo        = repository
        self.reward_calc = reward_calculator or RewardCalculator()
        self.EPISODE_LEN = episode_length

        self.node_msd_limits = MSD_LIMITS[:num_nodes].copy()
        self.latency_matrix  = LATENCY_MATRIX[:num_nodes, :num_nodes].copy()
        self.max_cpu         = 100.0
        self.max_ram         = 100.0

        obs_dim = num_nodes * self.NODE_FEAT_DIM + self.REQ_FEAT_DIM + self.TRAFFIC_DIM
        self.observation_space = spaces.Box(0.0, 1.0, shape=(obs_dim,), dtype=np.float32)
        self.action_space      = spaces.MultiDiscrete([num_nodes, num_nodes])

        # ── State ──────────────────────────────────────────────────
        self.current_step = 0
        self._state       = np.zeros(num_nodes * 3, dtype=np.float32)  # (N×3): cpu,ram,msd
        self._current_req = {'cpu': 0.0, 'ram': 0.0, 'msd': 1, 'service_type': 'Data'}

        # [NEW] Tracking previous assignment để tính switching cost
        self._prev_v1: int | None = None
        self._prev_v2: int | None = None

        # [NEW] Sliding window 20 bước gần nhất để track violation rate
        self._violation_window: deque = deque(maxlen=20)

    def update_reward_lambda(self, new_lambda: float) -> None:
        """Helper để đồng bộ lambda_latency từ Vectorized Env."""
        self.reward_calc.update_lambda_latency(new_lambda)

    # ─────────────────────────────────────────────────────────────
    #  Observation Builder
    # ─────────────────────────────────────────────────────────────
    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(
            self.num_nodes * self.NODE_FEAT_DIM + self.REQ_FEAT_DIM + self.TRAFFIC_DIM,
            dtype=np.float32
        )
        for i in range(self.num_nodes):
            cpu_u = self._state[i*3]     / self.max_cpu
            ram_u = self._state[i*3 + 1] / self.max_ram
            msd_u = self._state[i*3 + 2] / self.node_msd_limits[i]
            msd_f = max(0.0, 1.0 - msd_u)
            base  = i * self.NODE_FEAT_DIM
            obs[base], obs[base+1], obs[base+2], obs[base+3] = cpu_u, ram_u, msd_u, msd_f

        br = self.num_nodes * self.NODE_FEAT_DIM
        obs[br]   = self._current_req['cpu'] / self.max_cpu
        obs[br+1] = self._current_req['ram'] / self.max_ram
        obs[br+2] = self._current_req['msd'] / float(self.node_msd_limits.max())

        svc_map = {'Video': 0, 'VoIP': 1, 'Data': 2, 'IoT': 3, 'Attack': 4}
        obs[br + self.REQ_FEAT_DIM + svc_map.get(
            self._current_req.get('service_type', 'Data'), 2)] = 1.0
        return np.clip(obs, 0.0, 1.0)

    # ─────────────────────────────────────────────────────────────
    #  [NEW] Processing Latency
    # ─────────────────────────────────────────────────────────────
    def _proc_latency(self, node: int) -> float:
        """Độ trễ xử lý tại switch: tăng khi bảng MSD bị lấp đầy."""
        msd_used = self._state[node * 3 + 2]
        utilization = min(1.0, msd_used / self.node_msd_limits[node])
        return PROC_COEF_MS * utilization   # 0 → 0.3ms

    # ─────────────────────────────────────────────────────────────
    #  Gymnasium Interface
    # ─────────────────────────────────────────────────────────────
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step  = 0
        self._state        = np.zeros(self.num_nodes * 3, dtype=np.float32)
        self._current_req  = {'cpu': 0.0, 'ram': 0.0, 'msd': 1, 'service_type': 'Data'}
        self._prev_v1      = None
        self._prev_v2      = None
        self._violation_window.clear()
        return self._get_obs(), {}

    def step(self, action):
        v1, v2 = int(action[0]), int(action[1])
        row    = self.repo.get_next_entry(self.current_step)

        cpu_req = row['cpu']
        ram_req = row['ram']
        msd_req = row['msd']
        svc     = row.get('service_type', 'Data')
        self._current_req  = {'cpu': cpu_req, 'ram': ram_req,
                               'msd': msd_req, 'service_type': svc}
        is_elephant = (msd_req >= 4 or row['ddos'] == 1)

        # ── Resource Decay ──────────────────────────────────────
        for i in range(self.num_nodes):
            self._state[i*3]     = max(0.0, self._state[i*3]     - np.random.uniform(2.0, 8.0))
            self._state[i*3 + 1] = max(0.0, self._state[i*3 + 1] - np.random.uniform(1.0, 4.0))
            self._state[i*3 + 2] = max(0.0, self._state[i*3 + 2] - 1.0)

        # ── Constraint Check ────────────────────────────────────
        errors, is_valid = [], True
        if (self._state[v1*3] + cpu_req > self.max_cpu or
                self._state[v2*3] + cpu_req > self.max_cpu):
            is_valid = False; errors.append("CPU overflow")

        if self._state[v1*3+2] + msd_req > self.node_msd_limits[v1]:
            is_valid = False; errors.append(f"MSD violation node {v1} ({NAMES[v1]})")
        if self._state[v2*3+2] + msd_req > self.node_msd_limits[v2]:
            is_valid = False; errors.append(f"MSD violation node {v2} ({NAMES[v2]})")

        # ── [NEW] Processing Latency ────────────────────────────
        prop_latency  = float(self.latency_matrix[v1][v2])
        proc_latency  = self._proc_latency(v1) + self._proc_latency(v2)
        total_latency = prop_latency + proc_latency

        # ── [NEW] Switching flag ────────────────────────────────
        is_switching = (
            self._prev_v1 is not None and
            (v1 != self._prev_v1 or v2 != self._prev_v2)
        )

        # ── Reward ──────────────────────────────────────────────
        reward = self.reward_calc.calculate(
            is_valid=is_valid, errors=errors,
            is_elephant=is_elephant,
            latency=total_latency,
            cpu_req=cpu_req, msd_req=msd_req, max_cpu=self.max_cpu,
            node_v1=v1, node_v2=v2, service_type=svc,
            is_switching=is_switching
        )

        # ── State Update ────────────────────────────────────────
        if is_valid:
            self._state[v1*3]   += cpu_req
            self._state[v1*3+1] += ram_req
            self._state[v1*3+2] += msd_req
            self._state[v2*3]   += cpu_req
            self._state[v2*3+1] += ram_req
            self._state[v2*3+2] += msd_req

        # ── Track history (SLA Latency focus) ───────────────────
        self._prev_v1 = v1
        self._prev_v2 = v2
        
        # Vi phạm SLA nếu total_latency > threshold của svc
        threshold = self.LATENCY_THRESHOLDS.get(svc, 100.0)
        has_latency_viol = (total_latency > threshold)
        self._violation_window.append(1 if has_latency_viol else 0)

        self.current_step += 1
        done = (self.current_step >= self.EPISODE_LEN)
        info = {
            'is_elephant':   is_elephant,
            'error_log':     " | ".join(errors),
            'v1': NAMES[v1], 'v2': NAMES[v2],
            'prop_latency_ms': prop_latency,
            'proc_latency_ms': proc_latency,
            'total_latency_ms': total_latency,
            'is_switching':  is_switching,
            # [NEW] Violation rate cho AdaptivePenaltyCallback (Soft Constraints)
            'latency_violation_rate': (
                sum(self._violation_window) / len(self._violation_window)
                if self._violation_window else 0.0
            ),
            'accepted': is_valid,
        }
        return self._get_obs(), float(reward), done, False, info

    # ─────────────────────────────────────────────────────────────
    #  [NEW] Invalid Action Masking (dành cho MaskablePPO)
    # ─────────────────────────────────────────────────────────────
    def action_masks(self) -> np.ndarray:
        """Trả về boolean mask shape (2 * num_nodes,).

        Bố cục: [ mask_v1_node0, mask_v1_node1, ..., mask_v1_nodeN,
                  mask_v2_node0, mask_v2_node1, ..., mask_v2_nodeN ]
        Một slot = False nếu node đó CHẮC CHẮN vi phạm tài nguyên với request hiện tại.
        Điều này ép xác suất chọn node không khả dụng về 0 ngay trong Actor network.
        """
        cpu_req = self._current_req.get('cpu', 0.0)
        msd_req = self._current_req.get('msd', 1)
        masks = np.ones(2 * self.num_nodes, dtype=bool)
        for i in range(self.num_nodes):
            cpu_curr = self._state[i * 3]
            msd_curr = self._state[i * 3 + 2]
            feasible = (
                (cpu_curr + cpu_req <= self.max_cpu) and
                (msd_curr + msd_req <= self.node_msd_limits[i])
            )
            masks[i]                   = feasible   # slot cho v1
            masks[self.num_nodes + i]  = feasible   # slot cho v2
        # Đảm bảo luôn có ít nhất 1 action hợp lệ (tránh crash MaskablePPO)
        if not masks[:self.num_nodes].any():
            masks[:self.num_nodes] = True
        if not masks[self.num_nodes:].any():
            masks[self.num_nodes:] = True
        return masks
