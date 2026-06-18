"""
env.py — JO-VDPR RL Environment v6 (Phase 10 — Joint Proactive Evacuation)

Nâng cấp so với v9:
    [NEW] Multi-Topology: Tích hợp `TopologyManager` hỗ trợ N nodes bất kỳ (10, 14, 22).
    [NEW] GNN-Ready Observation (Kích thước động: N*6 + 13):
          - Thêm `Proactive Alert Flag`: Mô phỏng tín hiệu cảnh báo từ Bi-GRU.
          - Thêm `Geo Latency`: GAT nhận thức địa lý, không bị mù hướng.
    [NEW] Cung cấp cờ alert_v1, alert_v2 cho RewardCalculator phạt penalty cực nặng.
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random as _stdlib_random
from collections import deque
from typing import List, Optional, Union, Dict, Any

from src.core.interfaces.repository import IRepository
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import (
    TopologyManager,
    compute_request_latency,
    srv6_sid_processing_ms
)


class JOVDPREnv(gym.Env):
    # N*6 + 13
    NODE_FEAT_DIM  = 6   # cpu, ram, msd_used, msd_free, alert_flag, geo_latency
    REQ_FEAT_DIM   = 3   # cpu_req, ram_req, msd_req
    TRAFFIC_DIM    = 5   # Video, VoIP, Data, IoT, Attack
    GLOBAL_CTX_DIM = 5   # avg_cpu, avg_msd_res, req_intensity, srv6_norm, chain_norm

    LATENCY_THRESHOLDS = {
        'IoT':   10.0,
        'Video': 30.0,
        'VoIP':  50.0,
        'Data':  100.0,
        'Attack': 500.0
    }

    MAX_SRv6_OVERHEAD_MS: float = srv6_sid_processing_ms(6)

    def __init__(self,
                 repository: IRepository,
                 reward_calculator: Optional[RewardCalculator] = None,
                 topology_manager: Optional[TopologyManager] = None,
                 episode_length: int = 100,
                 enforce_msd_constraint: bool = True):
        super().__init__()
        self.repo        = repository
        self.reward_calc = reward_calculator or RewardCalculator()
        self.EPISODE_LEN = episode_length
        self.enforce_msd_constraint = enforce_msd_constraint
        self.alert_cpu_threshold = 0.80
        self.inference_sla_threshold = None
        
        self.topo = topology_manager if topology_manager else TopologyManager("vietnam")
        self.num_nodes   = self.topo.num_nodes
        self.node_names  = self.topo.names
        self.node_msd_limits = self.topo.msd_limits
        self.latency_matrix  = self.topo.latency_matrix
        self.max_cpu         = 100.0
        self.max_ram         = 100.0

        obs_dim = (self.num_nodes * self.NODE_FEAT_DIM
                   + self.REQ_FEAT_DIM
                   + self.TRAFFIC_DIM
                   + self.GLOBAL_CTX_DIM)
        self.observation_space = spaces.Box(0.0, 1.0, shape=(obs_dim,), dtype=np.float32)
        self.action_space      = spaces.Discrete(self.num_nodes * self.num_nodes)

        self.current_step  = 0
        self._state        = np.zeros(self.num_nodes * 3, dtype=np.float32)
        self._current_req  = {'cpu': 0.0, 'ram': 0.0, 'msd': 1, 'service_type': 'Data'}
        self._prev_v1: Optional[int] = None
        self._prev_v2: Optional[int] = None
        self._violation_window: deque = deque(maxlen=20)

        # SFC Lifecycle & Link Bandwidth (SDN Controller Layer — Internal State)
        self.active_flows: deque = deque()
        self.MAX_LINK_BW = 10_000.0  # Mbps (10 Gbps per fiber link)
        self._link_bw = np.full((self.num_nodes, self.num_nodes), self.MAX_LINK_BW, dtype=np.float32)

        # ── Benchmark-configurable parameters ──
        self.traffic_scenario: str = 'uniform'   # 'uniform' | 'bursty' | 'heavy_tail'
        self.arrival_rate: float = 1.0            # 1.0 = Stress (every step), 0.2 = Normal
        self.ttl_range: tuple = (100, 500)        # SFC lifetime range (steps)

        # Geographically pre-calculated context
        geo_ctx = self.topo.get_geographic_context()
        self._geo_norm = geo_ctx / (np.max(geo_ctx) + 1e-9)

    def update_reward_lambda(self, new_lambda: float) -> None:
        self.reward_calc.update_lambda_latency(new_lambda)

    def _encode_action(self, v1: int, v2: int) -> int:
        return int(v1) * self.num_nodes + int(v2)

    def _decode_action(self, action) -> tuple[int, int]:
        if np.isscalar(action):
            a = int(action)
            return a // self.num_nodes, a % self.num_nodes
        if isinstance(action, np.ndarray) and action.ndim == 0:
            a = int(action.item())
            return a // self.num_nodes, a % self.num_nodes
        return int(action[0]), int(action[1])

    def _load_request_for_step(self, step: int) -> None:
        row = self.repo.get_next_entry(step)

        cpu_req = row['cpu']
        ram_req = row['ram']
        msd_req = row['msd']
        svc = row.get('service_type', 'Data')

        if self.traffic_scenario == 'bursty':
            hour = (step // 500) % 24
            peak = (8 <= hour < 10) or (17 <= hour < 20)
            mult = 2.0 if peak else 0.7
            cpu_req = min(self.max_cpu * 0.85, cpu_req * mult)
        elif self.traffic_scenario == 'heavy_tail':
            rng = self.np_random if self.np_random is not None else np.random
            if rng.random() < 0.2:
                cpu_req = min(self.max_cpu * 0.70, cpu_req * 3.5)
                msd_req = min(int(self.node_msd_limits.max()) - 1, msd_req + 3)

        self._current_req = {
            'cpu': cpu_req,
            'ram': ram_req,
            'msd': msd_req,
            'service_type': svc,
            'ddos': row.get('ddos', 0),
        }

    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(self.observation_space.shape[0], dtype=np.float32)

        cpu_utils_raw = []
        msd_residuals = []
        # Simulate local Bi-GRU trigger: if CPU > 80%, flag fires
        for i in range(self.num_nodes):
            cpu_u = self._state[i * 3]     / self.max_cpu
            ram_u = self._state[i * 3 + 1] / self.max_ram
            msd_u = self._state[i * 3 + 2] / self.node_msd_limits[i]
            msd_f = max(0.0, 1.0 - msd_u)
            alert = 1.0 if cpu_u > self.alert_cpu_threshold else 0.0
            
            base  = i * self.NODE_FEAT_DIM
            obs[base], obs[base + 1], obs[base + 2], obs[base + 3] = cpu_u, ram_u, msd_u, msd_f
            obs[base + 4] = alert
            obs[base + 5] = float(self._geo_norm[i])
            
            cpu_utils_raw.append(cpu_u)
            msd_residuals.append(msd_f)

        br = self.num_nodes * self.NODE_FEAT_DIM
        obs[br]     = self._current_req['cpu'] / self.max_cpu
        obs[br + 1] = self._current_req['ram'] / self.max_ram
        obs[br + 2] = self._current_req['msd'] / float(self.node_msd_limits.max())

        svc_map = {'Video': 0, 'VoIP': 1, 'Data': 2, 'IoT': 3, 'Attack': 4}
        obs[br + self.REQ_FEAT_DIM + svc_map.get(
            self._current_req.get('service_type', 'Data'), 2)] = 1.0

        gc_base = br + self.REQ_FEAT_DIM + self.TRAFFIC_DIM
        avg_cpu       = float(np.mean(cpu_utils_raw))
        avg_msd_res   = float(np.mean(msd_residuals))
        req_intensity = obs[br]
        n_sids        = int(self._current_req.get('msd', 1))
        srv6_norm     = srv6_sid_processing_ms(n_sids) / max(self.MAX_SRv6_OVERHEAD_MS, 1e-9)
        chain_norm    = n_sids / float(self.node_msd_limits.max())

        obs[gc_base]     = avg_cpu
        obs[gc_base + 1] = avg_msd_res
        obs[gc_base + 2] = req_intensity
        obs[gc_base + 3] = float(np.clip(srv6_norm, 0.0, 1.0))
        obs[gc_base + 4] = float(np.clip(chain_norm, 0.0, 1.0))

        return np.clip(obs, 0.0, 1.0)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step  = 0
        self._state        = np.zeros(self.num_nodes * 3, dtype=np.float32)
        self._current_req  = {'cpu': 0.0, 'ram': 0.0, 'msd': 1, 'service_type': 'Data'}
        self._prev_v1      = None
        self._prev_v2      = None
        self._violation_window.clear()
        self.active_flows.clear()
        self._link_bw = np.full((self.num_nodes, self.num_nodes), self.MAX_LINK_BW, dtype=np.float32)
        self._load_request_for_step(self.current_step)
        return self._get_obs(), {}

    def step(self, action):
        v1, v2 = self._decode_action(action)

        # ══ PHASE 1: SFC Lifecycle Tick (ALWAYS runs, even on skipped steps) ══
        # Đồng hồ hệ thống PHẢI trôi đi 1 tick mỗi step, bất kể có request hay không.
        # Nếu không, VNF sẽ bị "đóng băng thời gian" và không bao giờ hết TTL.
        expired = []
        for flow in self.active_flows:
            flow["ttl"] -= 1
            if flow["ttl"] <= 0:
                expired.append(flow)
        for flow in expired:
            self.active_flows.remove(flow)
            fv1 = flow.get("placement_node", flow.get("v1"))
            fv2 = flow.get("routing_node", flow.get("v2"))
            cpu_alloc = flow.get("cpu_allocated", flow.get("cpu", 0))
            ram_alloc = flow.get("ram_allocated", flow.get("ram", 0))
            msd_alloc = flow.get("msd_allocated", flow.get("msd", 0))
            
            self._state[fv1 * 3]     = max(0.0, self._state[fv1 * 3]     - cpu_alloc)
            self._state[fv1 * 3 + 1] = max(0.0, self._state[fv1 * 3 + 1] - ram_alloc)
            self._state[fv2 * 3 + 2] = max(0.0, self._state[fv2 * 3 + 2] - msd_alloc)
            # Hoàn trả Link Bandwidth (SDN Controller Layer)
            if fv1 != fv2:
                self._link_bw[fv1][fv2] += flow["bw"]
                self._link_bw[fv2][fv1] += flow["bw"]

        # ══ PHASE 2: Arrival Rate Control (Normal Load: skip request) ══
        # Dù skip, đồng hồ đã tick ở Phase 1 → tài nguyên được giải phóng đúng.
        if self.arrival_rate < 1.0:
            rng = self.np_random if self.np_random is not None else np.random
            if rng.random() > self.arrival_rate:
                self.current_step += 1
                done = (self.current_step >= self.EPISODE_LEN)
                if not done:
                    self._load_request_for_step(self.current_step)
                return self._get_obs(), 0.0, done, False, {
                    'accepted': False, 'skipped': True, 'error_log': 'no_arrival',
                    'v1': '', 'v2': '', 'total_latency_ms': 0.0,
                    'prop_latency_ms': 0.0, 'srv6_latency_ms': 0.0,
                    'queue_latency_ms': 0.0, 'latency_threshold_ms': 0.0,
                    'is_switching': False, 'is_elephant': False,
                    'evacuation_hit': False, 'latency_violation_rate': 0.0,
                    'cpu_util_v1': 0.0, 'cpu_util_v2': 0.0,
                    'n_sids': 0, 'service_type': 'Data',
                }

        # ══ PHASE 3: Use request already exposed in observation/mask ══
        cpu_req = self._current_req['cpu']
        ram_req = self._current_req['ram']
        msd_req = self._current_req['msd']
        svc = self._current_req.get('service_type', 'Data')
        is_elephant = (msd_req >= 4 or self._current_req.get('ddos', 0) == 1)
        bw_req = cpu_req * 10.0  # BW demand proportional to CPU (Mbps)

        # ══ PHASE 4: Validation & Placement ══

        # [NEW] Path-aware MSD (Hop count included)
        hop_count = self.topo.get_hop_distance(v1, v2)
        msd_total = msd_req + hop_count

        # Trích cờ cảnh báo (Proactive Alert)
        alert_v1 = 1.0 if (self._state[v1 * 3] / self.max_cpu) > self.alert_cpu_threshold else 0.0
        alert_v2 = 1.0 if (self._state[v2 * 3] / self.max_cpu) > self.alert_cpu_threshold else 0.0

        errors, is_valid = [], True
        has_msd_violation = False

        if self._state[v1 * 3] + cpu_req > self.max_cpu:
            is_valid = False
            errors.append("CPU overflow at placement node")

        if self._state[v1 * 3 + 1] + ram_req > self.max_ram:
            is_valid = False
            errors.append("RAM overflow at placement node")

        if self._state[v2 * 3 + 2] + msd_total > self.node_msd_limits[v2]:
            if self.enforce_msd_constraint:
                is_valid = False
            has_msd_violation = True
            errors.append(f"MSD violation routing node {v2} (req:{msd_req}+hop:{hop_count})")

        # Bandwidth check (SDN Controller — Admission Control)
        if v1 != v2 and self._link_bw[v1][v2] < bw_req:
            is_valid = False
            errors.append(f"Link BW exhausted ({v1}->{v2})")

        cpu_util_v1 = min(1.0, self._state[v1 * 3] / self.max_cpu)
        cpu_util_v2 = min(1.0, self._state[v2 * 3] / self.max_cpu)

        latency_breakdown = compute_request_latency(
            v1=v1, v2=v2, n_sids=msd_req,
            cpu_util_v1=cpu_util_v1, cpu_util_v2=cpu_util_v2,
            latency_matrix=self.latency_matrix
        )
        total_latency = latency_breakdown["D_total_ms"]
        prop_latency  = latency_breakdown["D_prop_ms"]
        srv6_latency  = latency_breakdown["D_srv6_ms"]
        queue_latency = latency_breakdown["D_queue_ms"]

        if self.inference_sla_threshold is not None and total_latency > self.inference_sla_threshold:
            is_valid = False
            errors.append(f"Latency exceeds inference SLA threshold ({total_latency:.2f}ms > {self.inference_sla_threshold:.2f}ms)")

        is_switching = (self._prev_v1 is not None and (v1 != self._prev_v1 or v2 != self._prev_v2))

        # ══ PHASE 5: Reward Calculation ══
        reward = self.reward_calc.calculate(
            is_valid=is_valid, errors=errors,
            is_elephant=is_elephant,
            latency=total_latency,
            cpu_req=cpu_req, msd_req=msd_req, max_cpu=self.max_cpu,
            node_v1=v1, node_v2=v2, service_type=svc,
            is_switching=is_switching,
            alert_v1=alert_v1, alert_v2=alert_v2,
            cpu_util_v1=cpu_util_v1, cpu_util_v2=cpu_util_v2,
            has_msd_violation=has_msd_violation
        )

        if is_valid:
            self._state[v1 * 3]     += cpu_req
            self._state[v1 * 3 + 1] += ram_req
            self._state[v2 * 3 + 2] += msd_total
            # SFC Lifecycle: Đăng ký flow với TTL ngẫu nhiên
            ttl = int(self.np_random.integers(self.ttl_range[0], self.ttl_range[1])) if self.np_random is not None else np.random.randint(self.ttl_range[0], self.ttl_range[1])
            self.active_flows.append({
                "placement_node": v1,
                "routing_node": v2,
                "cpu_allocated": cpu_req,
                "ram_allocated": ram_req,
                "msd_allocated": msd_total,
                "bw": bw_req,
                "ttl": ttl
            })
            # Trừ Link Bandwidth (SDN Controller Layer)
            if v1 != v2:
                self._link_bw[v1][v2] -= bw_req
                self._link_bw[v2][v1] -= bw_req

        self._prev_v1 = v1
        self._prev_v2 = v2
        threshold = self.LATENCY_THRESHOLDS.get(svc, 80.0)
        has_latency_viol = (total_latency > threshold)
        self._violation_window.append(1 if has_latency_viol else 0)

        self.current_step += 1
        done = (self.current_step >= self.EPISODE_LEN)
        if not done:
            self._load_request_for_step(self.current_step)
        info = {
            'is_elephant':     is_elephant,
            'error_log':       " | ".join(errors),
            'v1':              self.node_names[v1],
            'v2':              self.node_names[v2],
            'prop_latency_ms': prop_latency,
            'srv6_latency_ms': srv6_latency,
            'queue_latency_ms':queue_latency,
            'total_latency_ms':total_latency,
            'latency_threshold_ms': threshold,
            'is_switching':    is_switching,
            'accepted':        is_valid,
            'msd_violation':   has_msd_violation,
            'admitted_msd_violation': bool(is_valid and has_msd_violation),
            'evacuation_hit':  (alert_v1 == 1.0 or alert_v2 == 1.0), # Tracking logic mới
            'latency_violation_rate': (sum(self._violation_window) / len(self._violation_window) if self._violation_window else 0.0),
            'cpu_util_v1':     cpu_util_v1,
            'cpu_util_v2':     cpu_util_v2,
            'n_sids':          msd_total,
            'service_type':    svc,
        }
        return self._get_obs(), float(reward), done, False, info

    def action_masks(self) -> np.ndarray:
        cpu_req = self._current_req.get('cpu', 0.0)
        ram_req = self._current_req.get('ram', 0.0)
        msd_req = self._current_req.get('msd', 1)
        bw_req = cpu_req * 10.0
        masks = np.zeros(self.num_nodes * self.num_nodes, dtype=bool)

        for place in range(self.num_nodes):
            cpu_curr = self._state[place * 3]
            ram_curr = self._state[place * 3 + 1]
            if cpu_curr + cpu_req > self.max_cpu or ram_curr + ram_req > self.max_ram:
                continue
            for route in range(self.num_nodes):
                if place != route and self._link_bw[place][route] < bw_req:
                    continue
                hop_count = self.topo.get_hop_distance(place, route)
                msd_curr = self._state[route * 3 + 2]
                if msd_curr + msd_req + hop_count <= self.node_msd_limits[route]:
                    masks[self._encode_action(place, route)] = True

        if not masks.any():
            masks[:] = True
        return masks
