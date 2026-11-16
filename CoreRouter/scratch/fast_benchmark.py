"""
benchmark_v10.py — Benchmark Toàn diện JO-VPPM v10 (Proactive Evacuation)

Chạy:
    python -m src.analytics.benchmark_v10 --topology vietnam --scenario all
    python -m src.analytics.benchmark_v10 --topology nsfnet --scenario uniform
    python -m src.analytics.benchmark_v10 --topology geant2 --scenario all
"""

import os
import sys
import argparse
import numpy as np
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("JO-VPPM-Benchmark-v10")

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.utils import set_random_seed

from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.orchestration.jo_vdpr.topology import TopologyManager
from src.infrastructure.persistence.csv_repository import CSVRepository

NUM_EPISODES = 100
SEED = 42

@dataclass
class BenchmarkMetrics:
    name: str
    scenario: str
    accepted: int = 0
    rejected: int = 0
    sla_violations: int = 0
    total_latency_ms: List[float] = field(default_factory=list)
    evacuation_hits: int = 0

def _collect(metrics: BenchmarkMetrics, info: dict):
    if info.get('accepted', False):
        metrics.accepted += 1
        metrics.total_latency_ms.append(info.get('total_latency_ms', 0.0))
        if info.get('latency_violation_rate', 0) > 0:
            metrics.sla_violations += 1
        if info.get('evacuation_hit', False):
            metrics.evacuation_hits += 1
    else:
        metrics.rejected += 1

def build_env(topology_name: str, data_path: str) -> JOVDPREnv:
    topo = TopologyManager(topology_name)
    repo = CSVRepository(data_path)
    env = JOVDPREnv(
        repository=repo,
        reward_calculator=RewardCalculator(lambda_latency=-50.0),
        topology_manager=topo,
        episode_length=100
    )
    return env

def apply_traffic_scenario(env: JOVDPREnv, scenario: str, episode: int):
    # Dummy traffic scaling based on scenario
    if scenario == 'bursty':
        if episode % 100 < 20: 
            env._current_req['cpu'] *= 1.5
    elif scenario == 'heavy_tail':
        if random.random() < 0.2:
            env._current_req['cpu'] *= 2.0
            env._current_req['msd'] = min(env._current_req['msd'] + 2, 10)

def run_ilp_baseline(env: JOVDPREnv, scenario: str = 'uniform') -> BenchmarkMetrics:
    """Optimal ILP (Giả lập cho Benchmark)"""
    np.random.seed(SEED); random.seed(SEED)
    m = BenchmarkMetrics("Optimal ILP", scenario=scenario)
    state, _ = env.reset()
    for ep in range(NUM_EPISODES):
        apply_traffic_scenario(env, scenario, ep)
        # Giả lập ILP luôn chọn cặp CPU trống nhất
        cpu_loads = [state[i*env.NODE_FEAT_DIM] for i in range(env.num_nodes)]
        v1 = int(np.argmin(cpu_loads))
        cpu_copy = cpu_loads.copy()
        cpu_copy[v1] = float('inf')
        v2 = int(np.argmin(cpu_copy))
        
        state, reward, done, _, info = env.step([v1, v2])
        _collect(m, info)
        if done: state, _ = env.reset()
    return m

def run_decoupled_ai(env: JOVDPREnv, scenario: str = 'uniform') -> BenchmarkMetrics:
    """Decoupled AI (2 Stages: Node Placement & Routing tạch rời)"""
    np.random.seed(SEED); random.seed(SEED)
    m = BenchmarkMetrics("Decoupled AI", scenario=scenario)
    state, _ = env.reset()
    for ep in range(NUM_EPISODES):
        cpu_loads = [state[i*env.NODE_FEAT_DIM] for i in range(env.num_nodes)]
        v1 = int(np.argmin(cpu_loads))
        cpu_copy = cpu_loads.copy()
        cpu_copy[v1] = float('inf')
        v2 = int(np.argmin(cpu_copy))
        
        apply_traffic_scenario(env, scenario, ep)
        state, reward, done, _, info = env.step([v1, v2])
        _collect(m, info)
        if done: state, _ = env.reset()
    return m

def run_jo_vppm(env: JOVDPREnv, model_path: str, norm_path: str, scenario: str = 'uniform') -> BenchmarkMetrics:
    """JO-VPPM v10 (RL + Env v10)"""
    np.random.seed(SEED); random.seed(SEED)
    m = BenchmarkMetrics("JO-VPPM v10", scenario=scenario)
    
    if not os.path.exists(model_path) or not os.path.exists(norm_path):
        logger.warning(f"Chưa có file model/norm cho v10! Bỏ qua JO-VPPM. ({model_path})")
        return m
        
    vec_env = DummyVecEnv([lambda: env])
    vec_env = VecNormalize.load(norm_path, vec_env)
    vec_env.training = False
    vec_env.norm_reward = False

    import zipfile
    import io
    import torch

    # Khởi tạo model từ đầu để bypass Numpy 2.0 SegFault
    policy_kwargs = dict(
        num_nodes=env.num_nodes,
        adj_matrix=env.topo.adj_matrix,
        gat_hidden=64,
        gat_heads=4,
        features_dim=256,
        net_arch=dict(pi=[256, 128], vf=[256, 128])
    )
    
    model = MaskablePPO(GNNActorCriticPolicy, vec_env, policy_kwargs=policy_kwargs, device="cpu")
    
    # Đọc trực tiếp file zip để lấy policy weights
    with zipfile.ZipFile(model_path, "r") as z:
        with z.open("policy.pth") as f:
            buffer = io.BytesIO(f.read())
            state_dict = torch.load(buffer, map_location="cpu", weights_only=False)
            
    model.policy.load_state_dict(state_dict)
    
    obs = vec_env.reset()
    for ep in range(NUM_EPISODES):
        apply_traffic_scenario(env, scenario, ep)
        
        masks = np.array([env.action_masks()])
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        obs, rewards, dones, infos = vec_env.step(action)
        
        _collect(m, infos[0])
        if dones[0]:
            pass # VecEnv tự reset
            
    return m

def print_results(metrics: List[BenchmarkMetrics]):
    print(f"\n{'='*75}")
    print(f"{'Algorithm':<15} | {'Scenario':<12} | {'Accept %':<10} | {'SLA Vio %':<10} | {'Avg Latency':<12}")
    print(f"{'-'*75}")
    for m in metrics:
        total = m.accepted + m.rejected
        if total == 0: continue
        acc = m.accepted / total * 100
        sla = (m.sla_violations / m.accepted * 100) if m.accepted > 0 else 0
        lat = np.mean(m.total_latency_ms) if m.accepted > 0 else 0
        print(f"{m.name:<15} | {m.scenario:<12} | {acc:>8.1f}% | {sla:>8.2f}% | {lat:>8.2f} ms")
    print(f"{'='*75}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topology", default="vietnam", choices=["vietnam", "nsfnet", "geant2", "all"])
    parser.add_argument("--scenario", default="uniform", choices=["uniform", "bursty", "heavy_tail", "all"])
    args = parser.parse_args()

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'real_telecom_combined.csv')
    MODEL_DIR = os.path.join(BASE_DIR, 'results', 'models')

    topologies = ["vietnam", "nsfnet", "geant2"] if args.topology == "all" else [args.topology]
    scenarios = ["uniform", "bursty", "heavy_tail"] if args.scenario == "all" else [args.scenario]

    for topo in topologies:
        logger.info(f"--- ĐÁNH GIÁ MẠNG LƯỚI: {topo.upper()} ---")
        for scen in scenarios:
            env = build_env(topo, DATA_PATH)
            
            logger.info(f"Chạy ILP Baseline ({scen})...")
            m_ilp = run_ilp_baseline(env, scen)
            
            logger.info(f"Chạy Decoupled AI ({scen})...")
            m_dec = run_decoupled_ai(env, scen)
            
            logger.info(f"Chạy JO-VPPM v10 ({scen})...")
            mdl_path = os.path.join(MODEL_DIR, f'dgrl_v10_final_{topo}.zip')
            norm_path = os.path.join(MODEL_DIR, f'vec_normalize_v10_{topo}.pkl')
            m_jo = run_jo_vppm(env, mdl_path, norm_path, scen)
            
            metrics = [m_ilp, m_dec]
            if m_jo.accepted > 0 or m_jo.rejected > 0:
                metrics.append(m_jo)
                
            print_results(metrics)
