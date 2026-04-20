"""
benchmark_eval.py — Đánh giá 4 nhóm thuật toán cho JO-VDPR (v4)

Cải tiến so với v3:
- Tương thích Phase 8 (MaskablePPO, Proportional Reward)
- Thêm metric: Processing Latency, Switching Cost
- Tự động load model Phase 8 (dgrl_v8.zip)
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("JO-VDPR-Benchmark")

from sb3_contrib import MaskablePPO
from stable_baselines3 import PPO

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '..', '..'))
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy

NUM_EPISODES = 5000   # Stress-Test Scale
WINDOW_SIZE  = 100    # Window cho rolling stats

@dataclass
class BenchmarkMetrics:
    name: str
    acceptance_list: List[bool] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    latencies: List[float] = field(default_factory=list)
    msd_violations: List[bool] = field(default_factory=list)
    cpu_variance: List[float] = field(default_factory=list)
    energy_index: float = 0.0
    sla_compliance: Dict[str, List[bool]] = field(default_factory=lambda: {
        'IoT': [], 'Video': [], 'VoIP': [], 'Data': [], 'Attack': []
    })

    @property
    def acceptance_rate(self):
        return sum(self.acceptance_list) / len(self.acceptance_list) * 100 if self.acceptance_list else 0

    @property
    def msd_viol_rate(self):
        return sum(self.msd_violations) / len(self.msd_violations) * 100 if self.msd_violations else 0

    @property
    def avg_latency(self):
        return np.mean(self.latencies) if self.latencies else 0

    @property
    def avg_cpu_var(self):
        return np.mean(self.cpu_variance) if self.cpu_variance else 0


# ═══════════════════════════════════════════════════════════════════════
#  BASELINE 1: Optimal ILP (Exhaustive Search trong testbed nhỏ)
# ═══════════════════════════════════════════════════════════════════════
def run_ilp_optimal(env):
    """Upper bound lý thuyết: Duyệt n² combinations, chọn action tốt nhất."""
    np.random.seed(42)
    random.seed(42)
    metrics = BenchmarkMetrics("Optimal (ILP)")
    state, _ = env.reset()

    for ep in range(NUM_EPISODES):
        best_action, best_reward = None, -float('inf')
        
        # Snapshot state
        saved_state = env._state.copy()
        saved_req   = dict(env._current_req)
        saved_step  = env.current_step

        # Optimized loop
        for v1 in range(env.num_nodes):
            for v2 in range(env.num_nodes):
                env._state, env._current_req, env.current_step = saved_state.copy(), dict(saved_req), saved_step
                _, r, _, _, _ = env.step([v1, v2])
                if r > best_reward:
                    best_reward, best_action = r, [v1, v2]
        
        if (ep + 1) % 500 == 0:
            print(f"    ... Finished {ep + 1}/{NUM_EPISODES} episodes")

        # Execute best
        env._state, env._current_req, env.current_step = saved_state.copy(), dict(saved_req), saved_step
        _, reward, done, _, info = env.step(best_action)
        
        # Collect Metrics
        metrics.acceptance_list.append(reward > 0)
        metrics.rewards.append(reward)
        metrics.latencies.append(info.get('total_latency_ms', 0))
        metrics.msd_violations.append('MSD' in info.get('error_log', ''))
        
        # Power & Balance
        cpu_utils = [env._state[i*3]/env.max_cpu for i in range(env.num_nodes)]
        metrics.cpu_variance.append(np.std(cpu_utils))
        metrics.energy_index += sum([100 + 150 * u for u in cpu_utils])

        if done: env.reset()

    return metrics

def run_nsf_greedy(env):
    """Heuristic: Luôn chọn Node 0 và Node 1."""
    np.random.seed(42)
    random.seed(42)
    metrics = BenchmarkMetrics("NSF (Greedy)")
    state, _ = env.reset()

    for _ in range(NUM_EPISODES):
        action = [0, 1]
        _, reward, done, _, info = env.step(action)
        
        metrics.acceptance_list.append(reward > 0)
        metrics.rewards.append(reward)
        metrics.latencies.append(info.get('total_latency_ms', 0))
        metrics.msd_violations.append('MSD' in info.get('error_log', ''))
        
        cpu_utils = [env._state[i*3]/env.max_cpu for i in range(env.num_nodes)]
        metrics.cpu_variance.append(np.std(cpu_utils))
        metrics.energy_index += sum([100 + 150 * u for u in cpu_utils])

        if done: env.reset()

    return metrics


# ═══════════════════════════════════════════════════════════════════════
#  BASELINE 3: Decoupled AI (Topology-Blind, 2-stage sequential)
# ═══════════════════════════════════════════════════════════════════════
def run_decoupled_ai(env):
    """Stage 1: Max Free CPU, Stage 2: Static Offset."""
    np.random.seed(42)
    random.seed(42)
    metrics = BenchmarkMetrics("Decoupled AI")
    state, _ = env.reset()

    for _ in range(NUM_EPISODES):
        cpu_used_norm = [state[i * 3] for i in range(env.num_nodes)]
        v1 = int(np.argmin(cpu_used_norm))
        v2 = (v1 + 2) % env.num_nodes

        new_state, reward, terminated, truncated, info = env.step([v1, v2])
        done = terminated or truncated
        
        metrics.acceptance_list.append(reward > 0)
        metrics.rewards.append(reward)
        metrics.latencies.append(info.get('total_latency_ms', 0))
        metrics.msd_violations.append('MSD' in info.get('error_log', ''))
        
        cpu_utils = [env._state[i*3]/env.max_cpu for i in range(env.num_nodes)]
        metrics.cpu_variance.append(np.std(cpu_utils))
        metrics.energy_index += sum([100 + 150 * u for u in cpu_utils])
        
        if done: state, _ = env.reset()
        else: state = new_state

    return metrics


# ═══════════════════════════════════════════════════════════════════════
#  SẢN PHẨM: JO-VDPR PPO (Joint Optimization — Centralized RL)
# ═══════════════════════════════════════════════════════════════════════
def run_jo_vdpr_ppo(env, model_path):
    """JO-VDPR: PPO với hardware-aware reward và GAT topology knowledge."""
    if not os.path.exists(model_path):
        return BenchmarkMetrics("JO-VDPR (N/A)")

    custom_objects = {"policy_class": GNNActorCriticPolicy}
    try:
        model = MaskablePPO.load(model_path, custom_objects=custom_objects)
    except Exception:
        model = PPO.load(model_path, custom_objects=custom_objects)

    np.random.seed(42)
    random.seed(42)
    metrics = BenchmarkMetrics("JO-VDPR (Ours)")
    state, _ = env.reset()

    for _ in range(NUM_EPISODES):
        masks = env.action_masks()
        action, _ = model.predict(state, action_masks=masks, deterministic=True)
        new_state, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        
        metrics.acceptance_list.append(reward > 0)
        metrics.rewards.append(reward)
        metrics.latencies.append(info.get('total_latency_ms', 0))
        metrics.msd_violations.append('MSD' in info.get('error_log', ''))
        
        cpu_utils = [env._state[i*3]/env.max_cpu for i in range(env.num_nodes)]
        metrics.cpu_variance.append(np.std(cpu_utils))
        metrics.energy_index += sum([100 + 150 * u for u in cpu_utils])
        
        if done: state, _ = env.reset()
        else: state = new_state

    return metrics


# ═══════════════════════════════════════════════════════════════════════
#  ROLLING STATS (cho box plot)
# ═══════════════════════════════════════════════════════════════════════
def run_with_rolling_stats(env, runner_fn, model_path=None, n_windows=20):
    """
    Chạy benchmark và chia thành n_windows cửa sổ để tính variance.
    Trả về list acceptance rate per window → dùng cho box plot.
    """
    window_ep  = NUM_EPISODES // n_windows
    acc_list   = []
    env.reset()

    for w in range(n_windows):
        accepts_in_window = 0
        for _ in range(window_ep):
            state = env._get_obs()
            if model_path:
                model = getattr(runner_fn, '_model_cache', None)
                if model is None:
                    try:
                        model = MaskablePPO.load(model_path)
                    except:
                        model = PPO.load(model_path)
                    runner_fn._model_cache = model
                action, _ = model.predict(state, deterministic=True)
            else:
                action = runner_fn(env, state)
            _, reward, done, _, _ = env.step(action)
            if reward > 0:
                accepts_in_window += 1
            if done:
                env.reset()
        acc_list.append(accepts_in_window / window_ep * 100)

    return acc_list


# ═══════════════════════════════════════════════════════════════════════
#  PLOTTING
# ═══════════════════════════════════════════════════════════════════════
def plot_acceptance_ratio(labels, acc_rates, msd_viol_rates, filepath):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    colors = ['#94a3b8', '#ef4444', '#f59e0b', '#10b981', '#6366f1']

    # ── Bar chart: Acceptance Ratio ──
    bars = ax1.bar(labels, acc_rates, color=colors[:len(labels)], width=0.6, zorder=2)
    ax1.set_ylabel('Acceptance Ratio (%)', fontsize=12)
    ax1.set_title('Tỉ lệ đáp ứng luồng SFC\n(Không vi phạm Hardware MSD Limits)', fontsize=12)
    ax1.set_ylim(0, 110)
    ax1.grid(axis='y', alpha=0.3, zorder=1)
    for bar, val in zip(bars, acc_rates):
        ax1.text(bar.get_x() + bar.get_width()/2, val + 1.5,
                 f"{val:.1f}%", ha='center', va='bottom', fontweight='bold', fontsize=11)

    # ── Bar chart: MSD Violation Rate ──
    bars2 = ax2.bar(labels, msd_viol_rates, color=colors[:len(labels)], width=0.6,
                    alpha=0.85, zorder=2)
    ax2.set_ylabel('MSD Violation Rate (%)', fontsize=12)
    ax2.set_title('Tỉ lệ vi phạm Hardware MSD\n(Thấp hơn = Tốt hơn)', fontsize=12)
    ax2.set_ylim(0, max(msd_viol_rates) * 1.25 + 5)
    ax2.grid(axis='y', alpha=0.3, zorder=1)
    for bar, val in zip(bars2, msd_viol_rates):
        ax2.text(bar.get_x() + bar.get_width()/2, val + 0.5,
                 f"{val:.1f}%", ha='center', va='bottom', fontweight='bold', fontsize=11)

    plt.suptitle(f'Benchmark JO-VDPR vs Baselines ({NUM_EPISODES} Network Requests)',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✅ Saved: {filepath}")


def plot_cumulative_reward(labels, rewards, filepath):
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#94a3b8', '#ef4444', '#f59e0b', '#10b981', '#6366f1']
    bars = ax.bar(labels, rewards, color=colors[:len(labels)], width=0.6, zorder=2)
    ax.axhline(0, color='black', linewidth=1)
    ax.set_ylabel('Cumulative Reward / Penalty Score', fontsize=12)
    ax.set_title(f'Hiệu năng Tối ưu Hóa Toán học\n(Tổng Reward sau {NUM_EPISODES} Network Requests)',
                 fontsize=12)
    ax.grid(axis='y', alpha=0.3, zorder=1)
    for bar in bars:
        yval = bar.get_height()
        offset = 5000 if yval > 0 else -20000
        va = 'bottom' if yval > 0 else 'top'
        ax.text(bar.get_x() + bar.get_width()/2, yval + offset,
                f"{int(yval):,}", ha='center', va=va, fontweight='bold', fontsize=11)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✅ Saved: {filepath}")


def plot_comparison_v1_v2(labels_v1, acc_v1, labels_v2, acc_v2, filepath):
    """So sánh kết quả trước (v1) và sau (v2) cải tiến."""
    x = np.arange(len(labels_v2))
    width = 0.35
    fig, ax = plt.subplots(figsize=(12, 6))

    # v1 bars (chỉ vẽ nếu có data)
    if acc_v1:
        bars1 = ax.bar(x - width/2, acc_v1, width, label='Before (v1 — 2k dataset)',
                       color='#94a3b8', alpha=0.8)
        for b, v in zip(bars1, acc_v1):
            ax.text(b.get_x()+b.get_width()/2, v+1, f"{v:.1f}%",
                    ha='center', fontsize=9, color='#475569')

    bars2 = ax.bar(x + (width/2 if acc_v1 else 0), acc_v2, width,
                   label='After (v2 — 50k real dataset)', color='#10b981')
    for b, v in zip(bars2, acc_v2):
        ax.text(b.get_x()+b.get_width()/2, v+1, f"{v:.1f}%",
                ha='center', fontsize=10, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(labels_v2)
    ax.set_ylabel('Acceptance Ratio (%)')
    ax.set_title('So sánh Trước/Sau Cải Tiến JO-VDPR\n(Dataset 2k → 50k, Reward Function v2)',
                 fontsize=13)
    ax.set_ylim(0, 115)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
def plot_stress_test_dashboard(all_metrics: List[BenchmarkMetrics], filepath: str):
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    colors = ['#94a3b8', '#ef4444', '#f59e0b', '#10b981']
    labels = [m.name for m in all_metrics]

    # 1. Acceptance Rate
    accs = [m.acceptance_rate for m in all_metrics]
    axes[0, 0].bar(labels, accs, color=colors)
    axes[0, 0].set_title("Acceptance Ratio (%)")
    axes[0, 0].set_ylim(0, 110)

    # 2. Cumulative Reward
    rews = [sum(m.rewards) for m in all_metrics]
    axes[0, 1].bar(labels, rews, color=colors)
    axes[0, 1].set_title("Cumulative Utility (Reward)")

    # 3. Average Latency
    lats = [m.avg_latency for m in all_metrics]
    axes[0, 2].bar(labels, lats, color=colors)
    axes[0, 2].set_title("Avg Latency (ms)")

    # 4. Energy Index
    energies = [m.energy_index / 1e6 for m in all_metrics]  # Scaled
    axes[1, 0].bar(labels, energies, color=colors)
    axes[1, 0].set_title("Energy Consumption Index (MJ)")

    # 5. Load Balance (CPU Variance)
    vars = [m.avg_cpu_var for m in all_metrics]
    axes[1, 1].bar(labels, vars, color=colors)
    axes[1, 1].set_title("Avg CPU Load Variance (Lower=Better)")

    # 6. MSD Violations
    viols = [m.msd_viol_rate for m in all_metrics]
    axes[1, 2].bar(labels, viols, color=colors)
    axes[1, 2].set_title("MSD Violation Rate (%)")

    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    plt.close()

def plot_radar_chart(all_metrics: List[BenchmarkMetrics], filepath: str):
    from math import pi
    categories = ['Acceptance', 'Utility', 'Safety (1-Viol)', 'Latency', 'Balance']
    N = len(categories)
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)
    
    colors = ['#94a3b8', '#ef4444', '#f59e0b', '#10b981']
    
    for i, m in enumerate(all_metrics):
        # Normalize stats for radar
        values = [
            m.acceptance_rate / 100,
            sum(m.rewards) / 1.5e5,  # Estimate max
            (100 - m.msd_viol_rate) / 100,
            max(0, (100 - m.avg_latency) / 100),
            max(0, (1 - m.avg_cpu_var*5))
        ]
        values += values[:1]
        angles = [n / float(N) * 2 * pi for n in range(N)]
        angles += angles[:1]
        
        ax.plot(angles, values, linewidth=2, linestyle='solid', label=m.name, color=colors[i])
        ax.fill(angles, values, colors[i], alpha=0.1)

    plt.xticks(angles[:-1], categories)
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    plt.savefig(filepath, dpi=150)
    plt.close()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.join(base_dir, '..', '..')
    repo = CSVRepository(os.path.join(root_dir, 'data', 'real_telecom_combined.csv'))
    reward_calc = RewardCalculator(lambda_latency=-300.0)
    env_eval = JOVDPREnv(repository=repo, reward_calculator=reward_calc, num_nodes=10)
    model_path = os.path.join(root_dir, 'results', 'models', 'dgrl_v8.zip')

    print(f"Starting Stress-Test Benchmark ({NUM_EPISODES} requests)...")
    
    m_opt = run_ilp_optimal(env_eval)
    print(f"Done Optimal.")
    m_nsf = run_nsf_greedy(env_eval)
    print(f"Done Greedy.")
    m_dec = run_decoupled_ai(env_eval)
    print(f"Done Decoupled AI.")
    m_ppo = run_jo_vdpr_ppo(env_eval, model_path)
    print(f"Done JO-VDPR.")

    results = [m_opt, m_nsf, m_dec, m_ppo]
    fig_dir = os.path.join(root_dir, 'results', 'figures', 'benchmark_stress_test')
    os.makedirs(fig_dir, exist_ok=True)
    
    plot_stress_test_dashboard(results, os.path.join(fig_dir, 'dashboard_kpi.png'))
    plot_radar_chart(results, os.path.join(fig_dir, 'radar_comparison.png'))
    
    print(f"\nBenchmark Complete. Results saved in {fig_dir}")
    print("-" * 50)
    for m in results:
        print(f"{m.name: <15} | Acc: {m.acceptance_rate:.2f}% | Viol: {m.msd_viol_rate:.2f}% | Energy: {m.energy_index/1e6:.2f}MJ")
