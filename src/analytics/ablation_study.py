"""
ablation_study.py — Ablation Study cho JO-VPPM v10 

Cấu trúc 4 chiều Ablation:
  V1: JO-VPPM Full        — Đầy đủ tính năng (GAT, Masking, Proactive Evac)
  V2: GAT -> Mù Topology  — Thuật toán tham lam hoàn toàn hỏng bét về nhận thức đồ thị
  V3: w/o Action Masking  — Bỏ khiên chắn phần cứng MSD, để AI đi vào chỗ chết chóc
  V4: w/o Tối ưu Độ trễ    — Giảm mức phạt penalty latency xuống cực thấp (Fixed) -> Vi phạm SLA
"""

import os
import sys
import numpy as np
import random
import zipfile
import io
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import logging
from dataclasses import dataclass, field
from typing import List, Dict

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from src.orchestration.jo_vdpr.env       import JOVDPREnv
from src.orchestration.jo_vdpr.rewards   import RewardCalculator
from src.orchestration.jo_vdpr.topology  import TopologyManager
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.infrastructure.persistence.csv_repository import CSVRepository

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Ablation-V10")

NUM_EPISODES = 5000
SEED         = 42


# ══════════════════════════════════════════════════════════════
#  Metrics
# ══════════════════════════════════════════════════════════════
@dataclass
class AblationMetrics:
    name: str
    label: str
    acceptance:    List[bool]  = field(default_factory=list)
    rewards:       List[float] = field(default_factory=list)
    latencies:     List[float] = field(default_factory=list)
    msd_violations:List[bool]  = field(default_factory=list)
    sla_violations:List[bool]  = field(default_factory=list)
    latency_breakdown: Dict[str, List[float]] = field(default_factory=lambda: {
        'prop': [], 'srv6': [], 'queue': []
    })

    @property
    def acceptance_rate(self): return np.mean(self.acceptance)*100 if self.acceptance else 0
    @property
    def msd_viol_rate(self): return np.mean(self.msd_violations)*100 if self.msd_violations else 0
    @property
    def sla_viol_rate(self): return np.mean(self.sla_violations)*100 if self.sla_violations else 0
    @property
    def avg_latency(self): return float(np.mean(self.latencies)) if self.latencies else 0
    @property
    def cum_reward(self): return float(sum(self.rewards))

def _collect(m: AblationMetrics, reward: float, info: dict):
    m.acceptance.append(info.get('accepted', False))
    m.rewards.append(reward)
    lat = info.get('total_latency_ms', 0.0)
    m.latencies.append(lat)
    m.msd_violations.append('MSD' in info.get('error_log', ''))
    thr = info.get('latency_threshold_ms', 80.0)
    m.sla_violations.append(lat > thr)
    m.latency_breakdown['prop'].append(info.get('prop_latency_ms', 0.0))
    m.latency_breakdown['srv6'].append(info.get('srv6_latency_ms', 0.0))
    m.latency_breakdown['queue'].append(info.get('queue_latency_ms', 0.0))

def _load_model(env, mdl_path, norm_path):
    vec_env = DummyVecEnv([lambda: env])
    vec_env = VecNormalize.load(norm_path, vec_env)
    vec_env.training = False
    vec_env.norm_reward = False

    policy_kwargs = dict(
        num_nodes=env.topo.num_nodes, adj_matrix=env.topo.adj_matrix,
        gat_hidden=64, gat_heads=4, features_dim=256,
        net_arch=dict(pi=[256, 128], vf=[256, 128])
    )
    model = MaskablePPO(GNNActorCriticPolicy, vec_env, policy_kwargs=policy_kwargs, device="cpu")
    with zipfile.ZipFile(mdl_path, "r") as z:
        with z.open("policy.pth") as f:
            buf = io.BytesIO(f.read())
            model.policy.load_state_dict(torch.load(buf, map_location="cpu", weights_only=False))
    return model, vec_env


# ══════════════════════════════════════════════════════════════
#  V1: Full JO-VPPM (Đề xuất cốt lõi)
# ══════════════════════════════════════════════════════════════
def run_v1_full(make_env, mdl_path, norm_path) -> AblationMetrics:
    m = AblationMetrics("JO-VPPM Full (Ours)", "Full")
    np.random.seed(SEED); random.seed(SEED)
    raw_env = make_env()
    model, vec_env = _load_model(raw_env, mdl_path, norm_path)
    obs = vec_env.reset()
    for _ in range(NUM_EPISODES):
        masks = np.array([raw_env.action_masks()])
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        obs, rew, done, infos = vec_env.step(action)
        _collect(m, rew[0], infos[0])
    raw_env.close()
    return m

# ══════════════════════════════════════════════════════════════
#  V2: Khuyết GAT (Giả lập bằng heuristic)
# ══════════════════════════════════════════════════════════════
def run_v2_no_gat(make_env) -> AblationMetrics:
    m = AblationMetrics("w/o GAT (Blind)", "w/o GAT")
    np.random.seed(SEED); random.seed(SEED)
    env = make_env()
    state, _ = env.reset()
    for _ in range(NUM_EPISODES):
        # 1. Chọn v1 & v2 có CPU thấp nhất mà hoàn toàn bỏ qua liên kết địa lý.
        cpu_loads = [state[i * env.NODE_FEAT_DIM] for i in range(env.num_nodes)]
        v1 = int(np.argmin(cpu_loads))
        cpu_copy = cpu_loads.copy()
        cpu_copy[v1] = float('inf')
        v2 = int(np.argmin(cpu_copy))
        
        state, reward, done, _, info = env.step([v1, v2])
        _collect(m, reward, info)
        if done: state, _ = env.reset()
    env.close()
    return m

# ══════════════════════════════════════════════════════════════
#  V3: Khuyết Masking (Lỗi Phần Cứng MSD)
# ══════════════════════════════════════════════════════════════
def run_v3_no_mask(make_env, mdl_path, norm_path) -> AblationMetrics:
    m = AblationMetrics("w/o Masking", "w/o Mask")
    np.random.seed(SEED); random.seed(SEED)
    raw_env = make_env()
    model, vec_env = _load_model(raw_env, mdl_path, norm_path)
    obs = vec_env.reset()
    # All-True mask = model được phép chọn BẤT KỲ node nào, kể cả node đang vi phạm MSD
    # Đây là cách đúng để simulate "w/o Action Masking" trong MaskablePPO
    all_true_mask = np.ones((1, 2 * raw_env.num_nodes), dtype=bool)
    for _ in range(NUM_EPISODES):
        action, _ = model.predict(obs, action_masks=all_true_mask, deterministic=True)
        obs, rew, done, infos = vec_env.step(action)
        _collect(m, rew[0], infos[0])
    raw_env.close()
    return m

# ══════════════════════════════════════════════════════════════
#  V4: Khuyết Adaptive SLA 
# ══════════════════════════════════════════════════════════════
def run_v4_no_adapt(make_env, mdl_path, norm_path) -> AblationMetrics:
    m = AblationMetrics("w/o Adaptive λ", "w/o Adapt-λ")
    np.random.seed(SEED); random.seed(SEED)
    raw_env = make_env()
    # Suy giảm Penalty
    raw_env.reward_calc.lambda_latency = -5.0 
    
    model, vec_env = _load_model(raw_env, mdl_path, norm_path)
    obs = vec_env.reset()
    for _ in range(NUM_EPISODES):
        masks = np.array([raw_env.action_masks()])
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        obs, rew, done, infos = vec_env.step(action)
        _collect(m, rew[0], infos[0])
    raw_env.close()
    return m


# ══════════════════════════════════════════════════════════════
#  Plotting
# ══════════════════════════════════════════════════════════════
PALETTE = {"Full": "#10b981", "w/o GAT": "#6366f1", "w/o Mask": "#f59e0b", "w/o Adapt-λ": "#ef4444"}

def plot_ablation(results: List[AblationMetrics], fig_dir: str):
    labels = [m.label for m in results]
    colors = [PALETTE.get(m.label, "#94a3b8") for m in results]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f"Ablation Study: Component Contribution Analysis (JO-VPPM v10)\n{NUM_EPISODES:,} Requests",
                 fontsize=14, fontweight='bold')

    def bar(ax, values, title, ylabel, fmt=".1f", ymax=None):
        bars = ax.bar(labels, values, color=colors, width=0.55, edgecolor='black', linewidth=1)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        if ymax: ax.set_ylim(0, ymax)
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + (ymax or max(values)*0.02),
                    f"{v:{fmt}}", ha='center', va='bottom', fontweight='bold', fontsize=10)

    bar(axes[0, 0], [m.acceptance_rate for m in results], "① Acceptance Ratio (%) ↑", "%", ymax=110)
    bar(axes[0, 1], [m.msd_viol_rate for m in results], "② Hardware MSD Violation (%) ↓", "%")
    bar(axes[0, 2], [m.sla_viol_rate for m in results], "③ Network SLA Violation (%) ↓", "%")
    bar(axes[1, 0], [m.avg_latency for m in results], "④ Avg SLA Latency (ms) ↓", "ms")
    
    cum_rews = [m.cum_reward for m in results]
    bar(axes[1, 1], cum_rews, "⑤ Cumulative Reward ↑", "Reward", fmt=".0f")

    # Stacked Latency
    ax6 = axes[1, 2]
    x = np.arange(len(labels))
    w = 0.5
    props = [np.mean(m.latency_breakdown['prop']) for m in results]
    srv6s = [np.mean(m.latency_breakdown['srv6']) for m in results]
    queues = [np.mean(m.latency_breakdown['queue']) for m in results]

    ax6.bar(x, props, w, label='D_prop', color='#3b82f6')
    ax6.bar(x, srv6s, w, bottom=props, label='D_srv6', color='#f59e0b')
    ax6.bar(x, queues, w, bottom=[p+s for p, s in zip(props, srv6s)], label='D_queue', color='#ef4444')
    ax6.set_xticks(x); ax6.set_xticklabels(labels)
    ax6.set_title("⑥ Component Latency Breakdown", fontweight='bold')
    ax6.legend(); ax6.grid(axis='y', alpha=0.3)

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(os.path.join(fig_dir, 'ablation_dashboard.png'), dpi=200, bbox_inches='tight')
    plt.savefig(os.path.join(fig_dir, 'ablation_dashboard.pdf'), dpi=200, bbox_inches='tight', format='pdf')
    plt.close()
    
    logger.info("Saved ablation_dashboard.png and ablation_dashboard.pdf")

def print_table(results: List[AblationMetrics]):
    header = f"{'Variant':<22} | {'Accept%':>8} | {'MSD-Viol%':>10} | {'SLA-Viol%':>10} | {'Avg Lat(ms)':>12} | {'Cum Reward':>12}"
    print(f"\n{'═' * len(header)}\n{header}\n{'═' * len(header)}")
    for m in results:
        star = "★" if m.label == "Full" else " "
        print(f"{star}{m.name:<22} | {m.acceptance_rate:>8.2f} | {m.msd_viol_rate:>10.2f} | "
              f"{m.sla_viol_rate:>10.2f} | {m.avg_latency:>12.2f} | {m.cum_reward:>12,.0f}")
    print(f"{'═' * len(header)}")


if __name__ == "__main__":
    BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'real_telecom_combined.csv')
    if not os.path.exists(DATA_PATH):
        DATA_PATH = os.path.join(BASE_DIR, 'data', 'real_telecom_combined.csv')
        
    MDL_DIR   = os.path.join(BASE_DIR, 'results', 'models')
    FIG_DIR   = os.path.join(BASE_DIR, 'results', 'figures', 'ablation')
    os.makedirs(FIG_DIR, exist_ok=True)
    
    topo_name = "vietnam" # Mặc định chạy V10 Vietnam Network
    mdl_path  = os.path.join(MDL_DIR, f"dgrl_v10_final_{topo_name}.zip")
    norm_path = os.path.join(MDL_DIR, f"vec_normalize_v10_{topo_name}.pkl")

    def make_env():
        return JOVDPREnv(CSVRepository(DATA_PATH), RewardCalculator(-50.0), TopologyManager(topo_name))

    print(f"=== Bắt đầu Ablation Study trên Topology: {topo_name.upper()} ({NUM_EPISODES} reqs) ===")
    m1 = run_v1_full(make_env, mdl_path, norm_path)
    m2 = run_v2_no_gat(make_env)
    m3 = run_v3_no_mask(make_env, mdl_path, norm_path)
    m4 = run_v4_no_adapt(make_env, mdl_path, norm_path)

    all_res = [m1, m2, m3, m4]
    print_table(all_res)
    plot_ablation(all_res, FIG_DIR)
