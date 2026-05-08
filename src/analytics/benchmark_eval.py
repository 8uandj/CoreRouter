"""
benchmark_eval.py — Benchmark Toàn diện JO-VPPM v5 (Phase 9)

Cải tiến so với v4:
    [NEW]  NUM_EPISODES = 10,000 (tăng từ 5,000 để tăng độ tin cậy thống kê)
    [NEW]  3 Traffic Scenarios:
           - uniform:    Phân phối đều chuẩn (baseline)
           - bursty:     Poisson arrivals — λ thay đổi theo giờ (peak/off-peak)
           - heavy_tail: Pareto flow sizes — elephant + mice flows (80/20 rule)
    [NEW]  95% Bootstrap Confidence Intervals cho tất cả metrics
    [NEW]  Multi-topology: --topology {vietnam, nsfnet, geant2}
    [NEW]  Latency breakdown per algorithm (Prop/SRv6/Queue)
    [NEW]  SLA compliance rate per traffic class (Video/VoIP/IoT/Data)
    [NEW]  CDF latency distribution plot
    [NEW]  Rolling acceptance time-series (detect stability)
    [KEEP] Stress-test dashboard (6-panel)
    [KEEP] Radar chart (multi-KPI)
    [KEEP] Optimal ILP + NSF Greedy + Decoupled AI baselines

Chạy:
    python -m src.analytics.benchmark_eval --topology vietnam --scenario all
    python -m src.analytics.benchmark_eval --topology nsfnet --scenario uniform
    python -m src.analytics.benchmark_eval --topology all --scenario all
"""

import os
import sys
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("JO-VPPM-Benchmark-v5")

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from sb3_contrib import MaskablePPO
from stable_baselines3 import PPO

from src.orchestration.jo_vdpr.env       import JOVDPREnv
from src.orchestration.jo_vdpr.rewards   import RewardCalculator
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.infrastructure.persistence.csv_repository import CSVRepository

NUM_EPISODES    = 10_000
WINDOW_SIZE     = 100      # Rolling window
N_BOOTSTRAP     = 500      # Bootstrap resamples for 95% CI
SEED            = 42


# ══════════════════════════════════════════════════════════════
#  Topology Builder
# ══════════════════════════════════════════════════════════════
def build_topology_env(topology: str, data_path: str) -> JOVDPREnv:
    """Tạo env phù hợp topology được chọn."""
    reward_calc = RewardCalculator(lambda_latency=-50.0, knapsack_scale=0.5)

    if topology == 'vietnam':
        from src.orchestration.jo_vdpr.topology import NUM_NODES, NAMES
        num_nodes, node_names = NUM_NODES, NAMES
    elif topology == 'nsfnet':
        from src.orchestration.jo_vdpr.topology_nsfnet import (
            NUM_NODES_NSFNET, LATENCY_MATRIX_NSFNET, MSD_LIMITS_NSFNET, NAMES_NSFNET
        )
        num_nodes, node_names = NUM_NODES_NSFNET, NAMES_NSFNET
    elif topology == 'geant2':
        from src.orchestration.jo_vdpr.topology_geant2 import (
            NUM_NODES_GEANT2, LATENCY_MATRIX_GEANT2, MSD_LIMITS_GEANT2, NAMES_GEANT2
        )
        num_nodes, node_names = NUM_NODES_GEANT2, NAMES_GEANT2
    else:
        raise ValueError(f"Unknown topology: {topology}")

    repo = CSVRepository(data_path)
    env  = JOVDPREnv(
        repository=repo,
        reward_calculator=reward_calc,
        num_nodes=num_nodes,
        episode_length=100,
        node_names=node_names
    )

    # Patch latency/MSD nếu không phải Vietnam
    if topology == 'nsfnet':
        env.latency_matrix  = LATENCY_MATRIX_NSFNET[:num_nodes, :num_nodes].copy()
        env.node_msd_limits = MSD_LIMITS_NSFNET[:num_nodes].copy()
    elif topology == 'geant2':
        env.latency_matrix  = LATENCY_MATRIX_GEANT2[:num_nodes, :num_nodes].copy()
        env.node_msd_limits = MSD_LIMITS_GEANT2[:num_nodes].copy()

    return env


# ══════════════════════════════════════════════════════════════
#  Traffic Scenario Modifiers
# ══════════════════════════════════════════════════════════════
def apply_traffic_scenario(env: JOVDPREnv, scenario: str, step: int):
    """
    Điều chỉnh hành vi dataset theo traffic scenario.
    Vì dataset là file CSV cố định, ta điều chỉnh bằng cách
    scale cpu_req dựa trên scenario pattern.
    """
    if scenario == 'uniform':
        pass  # Không thay đổi — dùng dataset gốc
    elif scenario == 'bursty':
        # Poisson: λ thay đổi theo "giờ" (mỗi 500 steps = 1 giờ mô phỏng)
        hour      = (step // 500) % 24
        # Peak: 8-10h sáng và 17-20h chiều — tải tăng 2x
        peak_mult = 2.0 if (8 <= hour < 10 or 17 <= hour < 20) else 0.7
        env._current_req['cpu'] = min(env.max_cpu * 0.9,
                                      env._current_req.get('cpu', 10) * peak_mult)
    elif scenario == 'heavy_tail':
        # Pareto: 80% requests là "mice" (nhỏ), 20% là "elephant" (lớn)
        if random.random() < 0.2:  # Elephant flow
            env._current_req['cpu'] = min(env.max_cpu * 0.8,
                                          env._current_req.get('cpu', 10) * 3.5)
            env._current_req['msd'] = min(env.node_msd_limits.max(),
                                          env._current_req.get('msd', 2) + 2)


# ══════════════════════════════════════════════════════════════
#  Metrics
# ══════════════════════════════════════════════════════════════
@dataclass
class BenchmarkMetrics:
    name:            str
    topology:        str   = 'vietnam'
    scenario:        str   = 'uniform'
    acceptance:      List[bool]  = field(default_factory=list)
    rewards:         List[float] = field(default_factory=list)
    latencies:       List[float] = field(default_factory=list)
    msd_violations:  List[bool]  = field(default_factory=list)
    sla_violations:  List[bool]  = field(default_factory=list)
    cpu_variance:    List[float] = field(default_factory=list)
    energy_index:    float       = 0.0
    sla_per_class:   Dict[str, List[bool]] = field(default_factory=lambda: {
        'IoT': [], 'Video': [], 'VoIP': [], 'Data': [], 'Attack': []
    })
    latency_breakdown: Dict[str, List[float]] = field(default_factory=lambda: {
        'prop': [], 'srv6': [], 'queue': []
    })

    @property
    def acceptance_rate(self): return np.mean(self.acceptance) * 100 if self.acceptance else 0.0
    @property
    def msd_viol_rate(self):   return np.mean(self.msd_violations) * 100 if self.msd_violations else 0.0
    @property
    def sla_viol_rate(self):   return np.mean(self.sla_violations) * 100 if self.sla_violations else 0.0
    @property
    def avg_latency(self):     return float(np.mean(self.latencies)) if self.latencies else 0.0
    @property
    def avg_cpu_var(self):     return float(np.mean(self.cpu_variance)) if self.cpu_variance else 0.0
    @property
    def cum_reward(self):      return float(sum(self.rewards))

    def acceptance_ci_95(self) -> tuple:
        """95% Bootstrap Confidence Interval cho Acceptance Rate."""
        if len(self.acceptance) < 10:
            return (0.0, 0.0)
        data = np.array(self.acceptance, dtype=float)
        boots = [np.mean(np.random.choice(data, len(data), replace=True)) * 100
                 for _ in range(N_BOOTSTRAP)]
        return (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))

    def rolling_acceptance(self, window: int = WINDOW_SIZE) -> List[float]:
        if not self.acceptance:
            return []
        arr = np.array(self.acceptance, dtype=float)
        return [np.mean(arr[max(0, i - window):i + 1]) * 100
                for i in range(len(arr))]


def _collect(m: BenchmarkMetrics, reward: float, info: dict, env: JOVDPREnv):
    m.acceptance.append(reward > 0)
    m.rewards.append(reward)
    lat = info.get('total_latency_ms', 0.0)
    m.latencies.append(lat)
    m.msd_violations.append('MSD' in info.get('error_log', ''))
    threshold = info.get('latency_threshold_ms', 80.0)
    m.sla_violations.append(lat > threshold)

    svc = info.get('service_type', 'Data')
    if svc in m.sla_per_class:
        m.sla_per_class[svc].append(lat > threshold)

    m.latency_breakdown['prop'].append(info.get('prop_latency_ms', 0.0))
    m.latency_breakdown['srv6'].append(info.get('srv6_latency_ms', 0.0))
    m.latency_breakdown['queue'].append(info.get('queue_latency_ms', 0.0))

    cpu_utils = [env._state[i * 3] / env.max_cpu for i in range(env.num_nodes)]
    m.cpu_variance.append(float(np.std(cpu_utils)))
    m.energy_index += sum(100 + 150 * u for u in cpu_utils)


# ══════════════════════════════════════════════════════════════
#  Baselines
# ══════════════════════════════════════════════════════════════
def run_ilp_optimal(env: JOVDPREnv, scenario: str = 'uniform') -> BenchmarkMetrics:
    """Upper bound: O(n²) exhaustive search per request."""
    # Seed khác nhau cho mỗi scenario để tránh trùng lặp
    scen_seed = SEED + hash(scenario) % 1000
    np.random.seed(scen_seed); random.seed(scen_seed)
    
    m = BenchmarkMetrics("Optimal (ILP)", scenario=scenario)
    env.reset()
    for ep in range(NUM_EPISODES):
        best_action, best_reward = None, -float('inf')
        saved = (env._state.copy(), dict(env._current_req), env.current_step)
        for v1 in range(env.num_nodes):
            for v2 in range(env.num_nodes):
                env._state, env._current_req, env.current_step = saved[0].copy(), dict(saved[1]), saved[2]
                _, r, _, _, _ = env.step([v1, v2])
                if r > best_reward:
                    best_reward, best_action = r, [v1, v2]
        env._state, env._current_req, env.current_step = saved[0].copy(), dict(saved[1]), saved[2]
        apply_traffic_scenario(env, scenario, ep)
        _, reward, done, _, info = env.step(best_action)
        _collect(m, reward, info, env)
        if done: env.reset()
        if (ep + 1) % 1000 == 0:
            logger.info(f"  ILP: {ep + 1}/{NUM_EPISODES} | Acc: {m.acceptance_rate:.1f}%")
    return m


def run_nsf_greedy(env: JOVDPREnv, scenario: str = 'uniform') -> BenchmarkMetrics:
    """Heuristic: Always (Node 0, Node 1)."""
    scen_seed = SEED + hash(scenario) % 1000
    np.random.seed(scen_seed); random.seed(scen_seed)
    
    m = BenchmarkMetrics("NSF Greedy", scenario=scenario)
    env.reset()
    for ep in range(NUM_EPISODES):
        apply_traffic_scenario(env, scenario, ep)
        _, reward, done, _, info = env.step([0, 1])
        _collect(m, reward, info, env)
        if done: env.reset()
    return m


def run_decoupled_ai(env: JOVDPREnv, scenario: str = 'uniform') -> BenchmarkMetrics:
    """Topology-blind: Stage1=min-CPU, Stage2=static offset."""
    scen_seed = SEED + hash(scenario) % 1000
    np.random.seed(scen_seed); random.seed(scen_seed)
    
    m = BenchmarkMetrics("Decoupled AI", scenario=scenario)
    state, _ = env.reset()
    for ep in range(NUM_EPISODES):
        cpu_loads = [state[i * 4] for i in range(env.num_nodes)]
        v1 = int(np.argmin(cpu_loads))
        v2 = (v1 + 2) % env.num_nodes
        apply_traffic_scenario(env, scenario, ep)
        state, reward, terminated, truncated, info = env.step([v1, v2])
        _collect(m, reward, info, env)
        if terminated or truncated: state, _ = env.reset()
    return m


def run_jo_vppm(env: JOVDPREnv, model_path: str, scenario: str = 'uniform') -> BenchmarkMetrics:
    """JO-VPPM: MaskablePPO + GAT + Physics-Aware Latency."""
    version = "v9" if "v9" in model_path else "v8"
    m = BenchmarkMetrics(f"★ JO-VPPM (Ours, {version})", scenario=scenario)
    scen_seed = SEED + hash(scenario) % 1000
    np.random.seed(scen_seed); random.seed(scen_seed)

    if not os.path.exists(model_path):
        logger.warning(f"Model not found: {model_path}")
        return m

    try:
        model = MaskablePPO.load(model_path, custom_objects={"policy_class": GNNActorCriticPolicy})
        
        # [LIVE-PATCH] Để hỗ trợ Generalization (chạy model 10-node trên bất kỳ số node nào)
        extractor = model.policy.features_extractor
        if extractor.num_nodes != env.num_nodes:
            logger.info(f"🧬 Patching model for Generalization: {extractor.num_nodes} -> {env.num_nodes} nodes")
            extractor.num_nodes = env.num_nodes
            
            # Tạo ma trận kề mới phù hợp với topology mới
            adj_np = (env.latency_matrix < 15.0).astype(np.float32)
            adj_t  = torch.tensor(adj_np, dtype=torch.float32)
            deg    = adj_t.sum(1, keepdim=True).clamp(min=1e-9).sqrt()
            adj_norm = adj_t / (deg * deg.T)
            extractor.register_buffer('adj', adj_norm)

    except Exception as e:
        logger.error(f"Load error: {e}")
        return m

    import torch
    state, _ = env.reset()
    for ep in range(NUM_EPISODES):
        apply_traffic_scenario(env, scenario, ep)
        
        # [NEW] Manual prediction logic to bypass SB3's shape validation
        with torch.no_grad():
            obs_tensor = torch.as_tensor(state).unsqueeze(0).to(model.device)
            masks   = env.action_masks()
            masks_t = torch.as_tensor(masks).unsqueeze(0).to(model.device)
            
            dist = model.policy.get_distribution(obs_tensor, masks_t)
            action = dist.get_actions(deterministic=True).cpu().numpy()[0]
        
        state, reward, terminated, truncated, info = env.step(action)
        _collect(m, reward, info, env)
        if terminated or truncated: state, _ = env.reset()
        if (ep + 1) % 1000 == 0:
            logger.info(f"  JO-VPPM: {ep + 1}/{NUM_EPISODES} | Acc: {m.acceptance_rate:.1f}%")
    return m


# ══════════════════════════════════════════════════════════════
#  Plotting
# ══════════════════════════════════════════════════════════════
PALETTE = ['#94a3b8', '#ef4444', '#f59e0b', '#10b981']


def plot_main_dashboard(results: List[BenchmarkMetrics], fig_dir: str, suffix: str = ''):
    """6-panel KPI dashboard."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    labels = [m.name for m in results]
    colors = PALETTE[:len(results)]
    topo   = results[0].topology if results else ''
    sc     = results[0].scenario if results else ''

    fig.suptitle(
        f"JO-VPPM Benchmark: {topo.upper()} Topology — {sc.title()} Traffic\n"
        f"({NUM_EPISODES:,} SFC Requests, Seed={SEED})",
        fontsize=13, fontweight='bold'
    )

    def bar(ax, vals, title, ylabel, add_ci=False, ci_data=None):
        bars = ax.bar(labels, vals, color=colors, width=0.55, zorder=2,
                      edgecolor='white', linewidth=0.8)
        ax.set_title(title, fontsize=10, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(axis='y', alpha=0.3, linestyle='--', zorder=1)
        ax.tick_params(axis='x', labelsize=8, rotation=15)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(vals) * 0.01,
                    f"{v:.2f}", ha='center', va='bottom', fontsize=9, fontweight='bold')
        if add_ci and ci_data:
            for i, (lo, hi) in enumerate(ci_data):
                ax.errorbar(i, vals[i], yerr=[[vals[i] - lo], [hi - vals[i]]],
                            fmt='none', color='black', capsize=5, linewidth=1.5)

    # Panel 1: Acceptance + CI
    accs   = [m.acceptance_rate for m in results]
    ci_arr = [m.acceptance_ci_95() for m in results]
    bar(axes[0, 0], accs, "① Acceptance Ratio (%) ↑\nw/ 95% Bootstrap CI",
        "Acceptance (%)", add_ci=True, ci_data=ci_arr)
    axes[0, 0].set_ylim(0, 115)

    # Panel 2: MSD Violation
    bar(axes[0, 1], [m.msd_viol_rate for m in results],
        "② MSD Hardware Violation (%) ↓\n(SRv6 Constraint)", "MSD Violation (%)")

    # Panel 3: Avg Latency
    bar(axes[0, 2], [m.avg_latency for m in results],
        "③ Avg End-to-End Latency (ms) ↓\n(Physics-Aware Model)", "Latency (ms)")

    # Panel 4: Energy
    bar(axes[1, 0], [m.energy_index / 1e6 for m in results],
        "④ Energy Consumption Index (MJ) ↓", "Energy (MJ)")

    # Panel 5: Load Balance
    bar(axes[1, 1], [m.avg_cpu_var for m in results],
        "⑤ CPU Load Variance (SD) ↓\n(Lower = More Balanced)", "CPU Std Dev")

    # Panel 6: SLA Compliance per class — grouped bar
    ax6   = axes[1, 2]
    classes = ['IoT', 'Video', 'VoIP', 'Data']
    x6    = np.arange(len(classes))
    bar_w = 0.18
    for i, (m, c) in enumerate(zip(results, colors)):
        compliance = []
        for cls in classes:
            lst = m.sla_per_class.get(cls, [])
            compliance.append((1 - np.mean(lst)) * 100 if lst else 100.0)
        ax6.bar(x6 + i * bar_w - bar_w * len(results) / 2,
                compliance, bar_w, label=m.name, color=c, alpha=0.9)
    ax6.set_xticks(x6); ax6.set_xticklabels(classes)
    ax6.set_ylim(0, 115)
    ax6.set_title("⑥ SLA Compliance per Traffic Class (%)\n(Higher = Better)", fontsize=10, fontweight='bold')
    ax6.set_ylabel("SLA Compliance (%)")
    ax6.legend(fontsize=7, loc='lower left')
    ax6.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    path = os.path.join(fig_dir, f'dashboard_{suffix}.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"✅ Saved: {path}")


def plot_latency_cdf(results: List[BenchmarkMetrics], fig_dir: str, suffix: str = ''):
    """CDF of end-to-end latency."""
    fig, ax = plt.subplots(figsize=(10, 6))
    for m, c in zip(results, PALETTE):
        if not m.latencies: continue
        sorted_lat = np.sort(m.latencies)
        cdf        = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat)
        ax.plot(sorted_lat, cdf, label=m.name, color=c, linewidth=2.0)

    # Reference lines
    for thr, lbl, lstyle in [(10, 'IoT 10ms', '--'), (20, 'Video 20ms', ':'),
                              (30, 'VoIP 30ms', '-.'), (80, 'Data 80ms', '-.')]:
        ax.axvline(thr, color='gray', linestyle=lstyle, alpha=0.5, linewidth=1)
        ax.text(thr + 0.3, 0.02, lbl, fontsize=8, color='gray', rotation=90)

    ax.set_xlabel("End-to-End Latency (ms)", fontsize=11)
    ax.set_ylabel("CDF", fontsize=11)
    ax.set_title(f"Latency CDF — {results[0].topology.upper() if results else ''} "
                 f"({results[0].scenario.title() if results else ''} traffic)\n"
                 f"Reference lines: SLA thresholds per traffic class", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3, linestyle='--')
    plt.tight_layout()
    path = os.path.join(fig_dir, f'latency_cdf_{suffix}.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"✅ Saved: {path}")


def plot_rolling_acceptance(results: List[BenchmarkMetrics], fig_dir: str, suffix: str = ''):
    """Rolling acceptance ratio over time → stability analysis."""
    fig, ax = plt.subplots(figsize=(14, 5))
    for m, c in zip(results, PALETTE):
        rolling = m.rolling_acceptance(WINDOW_SIZE)
        if not rolling: continue
        ax.plot(rolling, label=m.name, color=c, linewidth=1.5, alpha=0.85)

    ax.set_xlabel(f"SFC Request Index (Rolling {WINDOW_SIZE}-request window)", fontsize=10)
    ax.set_ylabel("Rolling Acceptance Rate (%)", fontsize=10)
    ax.set_title(f"Algorithm Stability Over {NUM_EPISODES:,} Requests\n"
                 f"({results[0].scenario.title() if results else ''} Traffic, "
                 f"Rolling Window = {WINDOW_SIZE})", fontsize=11)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 110)
    ax.grid(alpha=0.3, linestyle='--')
    plt.tight_layout()
    path = os.path.join(fig_dir, f'rolling_acceptance_{suffix}.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"✅ Saved: {path}")


def plot_radar(results: List[BenchmarkMetrics], fig_dir: str, suffix: str = ''):
    from math import pi
    categories = ['Acceptance', 'Utility', 'Safety\n(1-Viol)', 'Latency\nScore', 'Balance']
    N = len(categories)
    fig = plt.figure(figsize=(8, 8))
    ax  = fig.add_subplot(111, polar=True)
    max_reward = max(abs(m.cum_reward) for m in results) + 1e-9
    for m, c in zip(results, PALETTE):
        vals = [
            m.acceptance_rate / 100,
            max(0.0, (m.cum_reward + max_reward) / (2 * max_reward)),
            max(0.0, (100 - m.msd_viol_rate) / 100),
            max(0.0, (100 - min(m.avg_latency, 100)) / 100),
            max(0.0, 1 - m.avg_cpu_var * 5),
        ]
        vals += vals[:1]
        angles = [n / N * 2 * pi for n in range(N)] + [0]
        ax.plot(angles, vals, linewidth=2, color=c, label=m.name)
        ax.fill(angles, vals, color=c, alpha=0.08)
    ax.set_thetagrids([n / N * 360 for n in range(N)], categories)
    ax.set_ylim(0, 1)
    ax.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1), fontsize=9)
    ax.set_title(f"Multi-KPI Radar: {results[0].topology.upper() if results else ''}",
                 fontsize=12, fontweight='bold', pad=20)
    plt.tight_layout()
    path = os.path.join(fig_dir, f'radar_{suffix}.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"✅ Saved: {path}")


def print_summary_table(results: List[BenchmarkMetrics]):
    header = (f"{'Algorithm':<22} | {'Topo':>8} | {'Scenario':>10} | "
              f"{'Acc%':>6} | {'CI-95%':>14} | {'MSD-V%':>7} | "
              f"{'SLA-V%':>7} | {'Lat(ms)':>8} | {'Energy(MJ)':>10}")
    sep = "═" * len(header)
    print(f"\n{sep}\n{header}\n{sep}")
    for m in results:
        lo, hi = m.acceptance_ci_95()
        star   = "★ " if "Ours" in m.name else "  "
        print(f"  {star}{m.name:<20} | {m.topology:>8} | {m.scenario:>10} | "
              f"{m.acceptance_rate:>6.2f} | [{lo:>5.1f}, {hi:>5.1f}] | "
              f"{m.msd_viol_rate:>7.2f} | {m.sla_viol_rate:>7.2f} | "
              f"{m.avg_latency:>8.2f} | {m.energy_index / 1e6:>10.2f}")
    print(sep)


# ══════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════
def run_one_scenario(topology: str, scenario: str, data_path: str,
                     model_path: str, root_dir: str):
    fig_dir = os.path.join(root_dir, 'results', 'figures', f'benchmark_{topology}_{scenario}')
    os.makedirs(fig_dir, exist_ok=True)
    suffix  = f"{topology}_{scenario}"

    logger.info(f"\n{'='*60}")
    logger.info(f"  Topology: {topology.upper()} | Scenario: {scenario.upper()}")
    logger.info(f"  Episodes: {NUM_EPISODES:,}")
    logger.info(f"{'='*60}")

    def make_env():
        return build_topology_env(topology, data_path)

    logger.info("[1/4] Running Optimal ILP...")
    m_ilp = run_ilp_optimal(make_env(), scenario)

    logger.info("[2/4] Running NSF Greedy...")
    m_nsf = run_nsf_greedy(make_env(), scenario)

    logger.info("[3/4] Running Decoupled AI...")
    m_dec = run_decoupled_ai(make_env(), scenario)

    logger.info("[4/4] Running JO-VPPM...")
    m_ppo = run_jo_vppm(make_env(), model_path, scenario)

    for m in [m_ilp, m_nsf, m_dec, m_ppo]:
        m.topology = topology
        m.scenario = scenario

    results = [m_ilp, m_nsf, m_dec, m_ppo]
    print_summary_table(results)

    plot_main_dashboard(results, fig_dir, suffix)
    plot_latency_cdf(results, fig_dir, suffix)
    plot_rolling_acceptance(results, fig_dir, suffix)
    plot_radar(results, fig_dir, suffix)

    logger.info(f"✅ Scenario done. Figures → {fig_dir}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JO-VPPM Benchmark v5")
    parser.add_argument('--topology', type=str, default='vietnam',
                        choices=['vietnam', 'nsfnet', 'geant2', 'all'],
                        help='Topology to evaluate on')
    parser.add_argument('--scenario', type=str, default='all',
                        choices=['uniform', 'bursty', 'heavy_tail', 'all'],
                        help='Traffic scenario')
    parser.add_argument('--episodes', type=int, default=NUM_EPISODES)
    args = parser.parse_args()

    if args.episodes != NUM_EPISODES:
        NUM_EPISODES = args.episodes

    base_dir   = os.path.dirname(os.path.abspath(__file__))
    root_dir   = os.path.join(base_dir, '..', '..')
    data_path  = os.path.join(root_dir, 'data', 'real_telecom_combined.csv')
    model_v9   = os.path.join(root_dir, 'results', 'models', 'dgrl_v9.zip')
    model_v8   = os.path.join(root_dir, 'results', 'models', 'dgrl_v8.zip')
    model_path = model_v9 if os.path.exists(model_v9) else model_v8
    logger.info(f"Using model: {os.path.basename(model_path)}")

    topologies = ['vietnam', 'nsfnet', 'geant2'] if args.topology == 'all' else [args.topology]
    scenarios  = ['uniform', 'bursty', 'heavy_tail'] if args.scenario == 'all' else [args.scenario]

    all_results = []
    for topo in topologies:
        for sc in scenarios:
            try:
                r = run_one_scenario(topo, sc, data_path, model_path, root_dir)
                all_results.extend(r)
            except Exception as e:
                logger.error(f"Failed {topo}/{sc}: {e}", exc_info=True)

    print(f"\n\n{'='*60}")
    print(f"  ALL RESULTS SUMMARY ({len(all_results)} runs)")
    print_summary_table(all_results)
    print(f"\n✅ Full benchmark complete!")
