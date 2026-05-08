"""
benchmark_v10_final.py — Benchmark chuẩn khoa học JO-VPPM v10

Quy trình:
  1. Mỗi baseline/model chạy trên env RIÊNG BIỆT (tránh tích lũy state)
  2. Traffic scenario (bursty/heavy_tail) áp dụng ĐÚNG TỪNG STEP
  3. JO-VPPM dùng VecNormalize đồng bộ với action_masks từ vec_env
  4. Cận trên là Exhaustive Pair-Search N² per step (upper bound)
  5. Decoupled AI là 2-stage greedy (CPU-greedy placement + RAM-greedy routing)

Chạy:
  python -m src.analytics.benchmark_v10_final --topology all --scenario all --steps 3000
  python -m src.analytics.benchmark_v10_final --topology vietnam --scenario bursty --steps 1000
"""

import os
import sys
import argparse
import random
import zipfile
import io
import copy
import torch
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from dataclasses import dataclass, field
from typing import List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("BenchmarkV10-Final")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import TopologyManager
from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy

EVAL_SEEDS = [42, 100, 2024, 8888, 9999]

# (Traffic shaping logic moved into env.step() — no longer needed here)


# ══════════════════════════════════════════════════════════════
#  Metrics Collector
# ══════════════════════════════════════════════════════════════
@dataclass
class RunMetrics:
    name: str
    scenario: str
    topology: str
    acceptance:   List[bool]  = field(default_factory=list)
    latencies:    List[float] = field(default_factory=list)
    rewards:      List[float] = field(default_factory=list)
    sla_viols:    List[bool]  = field(default_factory=list)
    evacuation_hits: List[bool] = field(default_factory=list)

    @property
    def acc_rate(self):    return np.mean(self.acceptance) * 100 if self.acceptance else 0.0
    @property
    def avg_lat(self):     return float(np.mean(self.latencies)) if self.latencies else 0.0
    @property
    def sla_rate(self):    return np.mean(self.sla_viols) * 100 if self.sla_viols else 0.0
    @property
    def evac_rate(self):   return np.mean(self.evacuation_hits) * 100 if self.evacuation_hits else 0.0
    @property
    def avg_reward(self):  return float(np.mean(self.rewards)) if self.rewards else 0.0

    def rolling_acceptance(self, window=200):
        if len(self.acceptance) < window:
            return np.array([self.acc_rate] * len(self.acceptance))
        arr = np.array(self.acceptance, dtype=float)
        ret = np.cumsum(arr)
        ret[window:] = ret[window:] - ret[:-window]
        return (ret[window - 1:] / window) * 100

    def collect(self, info: dict, reward: float):
        # Bỏ qua các step không có request đến (arrival_rate control)
        if info.get('skipped', False):
            return
        self.acceptance.append(bool(info.get('accepted', False)))
        self.rewards.append(reward)
        if info.get('accepted', False):
            lat = info.get('total_latency_ms', 0.0)
            self.latencies.append(lat)
            thr = info.get('latency_threshold_ms', 80.0)
            self.sla_viols.append(lat > thr)
        self.evacuation_hits.append(bool(info.get('evacuation_hit', False)))


# ══════════════════════════════════════════════════════════════
#  Baseline 1: Exhaustive Pair-Search (Greedy N²)
# ══════════════════════════════════════════════════════════════
def run_exhaustive_search(make_env, scenario: str, num_steps: int, seed: int = 42) -> RunMetrics:
    """Upper-bound: duyệt tất cả N×N cặp node, chọn cặp có Reward cao nhất."""
    env = make_env()
    env.traffic_scenario = scenario
    np.random.seed(seed); random.seed(seed)
    m = RunMetrics("Exhaustive Pair-Search", scenario, env.topo.topology_name)
    
    env.reset()
    for step in range(num_steps):
        # Lưu snapshot state trước khi thử
        snap_state = env._state.copy()
        snap_req   = dict(env._current_req)
        snap_step  = env.current_step

        # Exhaust N² để tìm best_action
        best_r, best_a = -np.inf, [0, 0]
        for v1 in range(env.num_nodes):
            for v2 in range(env.num_nodes):
                env._state      = snap_state.copy()
                env._current_req = dict(snap_req)
                env.current_step = snap_step
                _, r, _, _, _ = env.step([v1, v2])
                if r > best_r:
                    best_r, best_a = r, [v1, v2]

        # Chạy lại với best action để lấy kết quả thật
        env._state      = snap_state.copy()
        env._current_req = dict(snap_req)
        env.current_step = snap_step
        _, reward, done, _, info = env.step(best_a)

        m.collect(info, reward)
        if done:
            env.reset()

    env.close()
    logger.info(f"  [Exhaustive] Acc={m.acc_rate:.1f}% | SLA-viol={m.sla_rate:.1f}% | AvgLat={m.avg_lat:.2f}ms")
    return m


# ══════════════════════════════════════════════════════════════
#  Baseline 2: Decoupled AI (2-stage greedy)
# ══════════════════════════════════════════════════════════════
def run_decoupled(make_env, scenario: str, num_steps: int, seed: int = 42) -> RunMetrics:
    """
    Stage 1: Chọn v1 = node có CPU trống nhất (Placement).
    Stage 2: Chọn v2 = lân cận 1-hop của v1 có RAM trống nhất (Routing tách rời).
    Không có nhận thức về Alert/Latency — đây là baseline "Decoupled".
    """
    env = make_env()
    env.traffic_scenario = scenario
    np.random.seed(seed); random.seed(seed)
    m = RunMetrics("Decoupled AI", scenario, env.topo.topology_name)

    state, _ = env.reset()
    for step in range(num_steps):
        # Stage 1: min-CPU placement
        cpu_loads = [state[i * env.NODE_FEAT_DIM] for i in range(env.num_nodes)]
        v1 = int(np.argmin(cpu_loads))

        # Stage 2: routing sang 1-hop láng giềng có RAM rảnh nhất
        neighbors = np.where(env.topo.adj_matrix[v1] > 0)[0]
        if len(neighbors) > 0:
            ram_loads = [state[c * env.NODE_FEAT_DIM + 1] for c in neighbors]
            v2 = int(neighbors[np.argmin(ram_loads)])
        else:
            # Không có láng giềng → fallback min-CPU khác
            cpu_copy = cpu_loads.copy()
            cpu_copy[v1] = np.inf
            v2 = int(np.argmin(cpu_copy))

        state, reward, done, _, info = env.step([v1, v2])
        m.collect(info, reward)
        if done:
            state, _ = env.reset()

    env.close()
    logger.info(f"  [Decoupled] Acc={m.acc_rate:.1f}% | SLA-viol={m.sla_rate:.1f}% | AvgLat={m.avg_lat:.2f}ms")
    return m


# ══════════════════════════════════════════════════════════════
#  Model Evaluation: JO-VPPM v10 (Trained RL Agent)
# ══════════════════════════════════════════════════════════════
def run_traditional_greedy(make_env, scenario: str, num_steps: int, seed: int = 42) -> RunMetrics:
    """Traditional Greedy: Max-CPU placement + Shortest-path SFC-aware routing."""
    env = make_env()
    env.traffic_scenario = scenario
    np.random.seed(seed); random.seed(seed)
    m = RunMetrics("Traditional Greedy", scenario, env.topo.topology_name)

    state, _ = env.reset(seed=seed)
    for step in range(num_steps):
        # Placement: Node có CPU trống NHIỀU NHẤT
        free_cpu = [(env.max_cpu - env._state[i * 3]) for i in range(env.num_nodes)]
        v1 = int(np.argmax(free_cpu))
        # Routing: SFC-aware shortest path (min total D_prop through v1)
        best_v2, best_cost = v1, np.inf
        for v2_cand in range(env.num_nodes):
            cost = env.latency_matrix[v1][v2_cand]
            if cost < best_cost and v2_cand != v1:
                best_cost = cost
                best_v2 = v2_cand
        v2 = best_v2
        state, reward, done, _, info = env.step([v1, v2])
        m.collect(info, reward)
        if done: state, _ = env.reset(seed=seed)
    env.close()
    logger.info(f"  [Greedy]    Acc={m.acc_rate:.1f}% | SLA-viol={m.sla_rate:.1f}% | AvgLat={m.avg_lat:.2f}ms")
    return m


def run_jo_vppm(make_env, mdl_path: str, norm_path: str,
                scenario: str, num_steps: int, seed: int = 42, label: str = "★ JO-VPPM v10") -> RunMetrics:
    """
    Chạy evaluation cho thuật toán JO-VPPM v10.
    - Dùng MaskablePPO với GNN policy.
    - Traffic scenario được áp dụng bên trong env.step()
    """
    raw_env = make_env()
    raw_env.traffic_scenario = scenario
    np.random.seed(seed); random.seed(seed)
    m = RunMetrics(label, scenario, raw_env.topo.topology_name)

    if not os.path.exists(mdl_path) or not os.path.exists(norm_path):
        logger.warning(f"  [JO-VPPM] Model/Norm không tồn tại: {mdl_path}")
        raw_env.close()
        return m

    # Bọc env trong VecNormalize để normalize observation
    vec_env = DummyVecEnv([lambda: raw_env])
    vec_env = VecNormalize.load(norm_path, vec_env)
    vec_env.training = False
    vec_env.norm_reward = False

    # Khởi tạo model architecture và load weights
    policy_kwargs = dict(
        num_nodes=raw_env.topo.num_nodes,
        adj_matrix=raw_env.topo.adj_matrix,
        gat_hidden=64, gat_heads=4, features_dim=256,
        net_arch=dict(pi=[256, 128], vf=[256, 128])
    )
    model = MaskablePPO(GNNActorCriticPolicy, vec_env,
                        policy_kwargs=policy_kwargs, device="cpu")
    with zipfile.ZipFile(mdl_path, "r") as z:
        with z.open("policy.pth") as f:
            buf = io.BytesIO(f.read())
            model.policy.load_state_dict(
                torch.load(buf, map_location="cpu", weights_only=False))

    obs = vec_env.reset()  # obs đã được normalize qua VecNormalize

    for step in range(num_steps):
        # Lấy action mask từ raw_env (trước normalize)
        masks = np.array([raw_env.action_masks()])

        # Model predict trên normalized obs
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)

        obs, reward_arr, done_arr, infos = vec_env.step(action)
        info   = infos[0]
        reward = float(reward_arr[0])

        m.collect(info, reward)
        # VecEnv tự reset khi done — không cần gọi thủ công

    vec_env.close()
    logger.info(f"  [JO-VPPM]  Acc={m.acc_rate:.1f}% | SLA-viol={m.sla_rate:.1f}% | "
                f"AvgLat={m.avg_lat:.2f}ms | Evac-hit={m.evac_rate:.1f}%")
    return m


# ══════════════════════════════════════════════════════════════
#  Plotting — Xuất biểu đồ ra thư mục riêng từng kịch bản
# ══════════════════════════════════════════════════════════════
PALETTE = {
    "Exhaustive Pair-Search": "#2ca02c",
    "Decoupled AI":           "#1f77b4",
    "Traditional Greedy":     "#ff7f0e",
    "★ JO-VPPM v10 (Ours)": "#d62728",
}

def get_color(m: RunMetrics) -> str:
    for key, col in PALETTE.items():
        if key in m.name:
            return col
    return "#888888"

def plot_scenario(results: List[RunMetrics], fig_dir: str):
    os.makedirs(fig_dir, exist_ok=True)
    topo = results[0].topology.upper()
    scen = results[0].scenario.capitalize()

    # ── Figure 1: Dashboard tổng quan (4 subplots) ──
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"JO-VPPM v10 vs Baselines — {topo} Network | {scen} Traffic",
                 fontsize=14, fontweight='bold', y=0.98)
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    # 1a. Bar: Acceptance Rate
    ax1 = fig.add_subplot(gs[0, 0])
    names  = [m.name.replace("★ ", "") for m in results]
    colors = [get_color(m) for m in results]
    bars = ax1.bar(names, [m.acc_rate for m in results], color=colors, alpha=0.85)
    ax1.bar_label(bars, fmt='%.1f%%', padding=3, fontsize=9)
    ax1.set_ylim(0, 115); ax1.set_title("Acceptance Rate (%)")
    ax1.tick_params(axis='x', labelsize=8, rotation=15)

    # 1b. Bar: SLA Violation Rate
    ax2 = fig.add_subplot(gs[0, 1])
    bars2 = ax2.bar(names, [m.sla_rate for m in results], color=colors, alpha=0.85)
    ax2.bar_label(bars2, fmt='%.1f%%', padding=3, fontsize=9)
    ax2.set_title("SLA Violation Rate (%)")
    ax2.tick_params(axis='x', labelsize=8, rotation=15)

    # 1c. Bar: Average Latency
    ax3 = fig.add_subplot(gs[0, 2])
    bars3 = ax3.bar(names, [m.avg_lat for m in results], color=colors, alpha=0.85)
    ax3.bar_label(bars3, fmt='%.2f ms', padding=3, fontsize=9)
    ax3.set_title("Average Latency (ms)")
    ax3.tick_params(axis='x', labelsize=8, rotation=15)

    # 1d. Line: Rolling Acceptance (stability)
    ax4 = fig.add_subplot(gs[1, :2])
    for m in results:
        roll = m.rolling_acceptance(200)
        if len(roll) > 0:
            ax4.plot(roll, label=m.name.replace("★ ", ""),
                     color=get_color(m), lw=1.8, alpha=0.9)
    ax4.set_ylim(0, 110)
    ax4.set_title(f"Rolling Acceptance (window=200)")
    ax4.set_xlabel("Step"); ax4.set_ylabel("Acceptance Rate (%)")
    ax4.legend(fontsize=9); ax4.grid(alpha=0.3)

    # 1e. Radar KPI
    ax5 = fig.add_subplot(gs[1, 2], polar=True)
    categories = ['Accept\n(%)', 'Safety\n(1-SLA)', 'Low\nLatency', 'Evac\nAware']
    N = len(categories)
    angles = [n / N * 2 * np.pi for n in range(N)] + [0]
    ax5.set_xticks(angles[:-1])
    ax5.set_xticklabels(categories, fontsize=8)
    ax5.set_ylim(0, 1)
    max_lat = max(m.avg_lat for m in results if m.avg_lat > 0) or 1.0

    for m in results:
        safety   = 1.0 - m.sla_rate / 100.0
        low_lat  = max(0.0, 1.0 - m.avg_lat / max_lat)
        evac_aw  = m.evac_rate / 100.0 if m.evac_rate > 0 else 0.0
        vals = [m.acc_rate/100.0, safety, low_lat, evac_aw]
        vals += vals[:1]
        ax5.plot(angles, vals, color=get_color(m),
                 label=m.name.replace("★ ", ""), lw=2)
        ax5.fill(angles, vals, color=get_color(m), alpha=0.08)
    ax5.set_title("KPI Radar", pad=15, fontsize=10)
    ax5.legend(loc='upper right', bbox_to_anchor=(1.5, 1.1), fontsize=8)

    fig.savefig(os.path.join(fig_dir, "dashboard.png"), dpi=200, bbox_inches='tight')
    fig.savefig(os.path.join(fig_dir, "dashboard.pdf"), dpi=200, bbox_inches='tight', format='pdf')
    plt.close(fig)

    # ── Figure 2: Latency CDF (Accepted Requests Only) ──
    fig2, ax = plt.subplots(figsize=(9, 5))
    for m in results:
        # CHỈ lấy latency của accepted requests (loại bỏ rejected → lat=0)
        accepted_lats = [lat for lat, acc in zip(m.latencies, m.acceptance) if acc]
        if not accepted_lats: continue
        s   = np.sort(accepted_lats)
        cdf = np.arange(1, len(s)+1) / len(s)
        # Minh bạch: Legend ghi rõ Avg Latency + Acceptance Rate
        # → Loại bỏ cáo buộc Survivorship Bias
        avg_lat = np.mean(accepted_lats)
        lbl = f"{m.name.replace('★ ', '')} (Avg: {avg_lat:.1f}ms | Accepted: {m.acc_rate:.1f}%)"
        ax.plot(s, cdf, label=lbl, color=get_color(m), lw=2)

    # SLA reference lines (Realistic WAN thresholds)
    for thr, lbl, ls in [(10, 'URLLC 10ms', '--'), (30, 'Video 30ms', '-.'),
                          (50, 'VoIP 50ms', ':'), (100, 'Data 100ms', (0,(5,5)))]:
        ax.axvline(thr, color='gray', linestyle=ls, alpha=0.5, lw=1)
        ax.text(thr+0.3, 0.03, lbl, color='gray', fontsize=8, rotation=90)

    ax.set_xlim(0, 60)
    ax.set_xlabel("End-to-End Latency (ms)"); ax.set_ylabel("CDF")
    ax.set_title(f"Latency CDF (Accepted Only) — {topo} ({scen})")
    ax.legend(fontsize=7, loc='lower right'); ax.grid(alpha=0.25)
    plt.tight_layout()
    fig2.savefig(os.path.join(fig_dir, "latency_cdf.png"), dpi=200, bbox_inches='tight')
    fig2.savefig(os.path.join(fig_dir, "latency_cdf.pdf"), dpi=200, bbox_inches='tight', format='pdf')
    plt.close(fig2)

    logger.info(f"  ✅ Saved figures → {fig_dir}")


# ══════════════════════════════════════════════════════════════
#  Summary Table (Mean ± Std for multi-seed)
# ══════════════════════════════════════════════════════════════
import json

def print_table(results: List[RunMetrics]):
    header = (f"{'Algorithm':<28} | {'Topo':>7} | {'Scenario':>10} | "
              f"{'Acc%':>6} | {'SLA-Viol%':>9} | {'Avg Lat':>8} | {'Evac-Hit%':>9}")
    sep = "═" * len(header)
    print(f"\n{sep}\n{header}\n{sep}")
    for m in results:
        star = "★ " if "Ours" in m.name else "  "
        print(f"  {star}{m.name.replace('★ ',''):<26} | {m.topology:>7} | {m.scenario:>10} | "
              f"{m.acc_rate:>5.1f}% | {m.sla_rate:>8.2f}% | {m.avg_lat:>6.2f}ms | {m.evac_rate:>8.1f}%")
    print(sep)


def print_multi_seed_table(algo_runs: dict, topo: str, scen: str):
    """Print Mean ± Std table from multi-seed runs."""
    header = (f"{'Algorithm':<28} | {'Acc% (Mean±Std)':>18} | {'SLA-Viol% (Mean±Std)':>22} | "
              f"{'AvgLat (Mean±Std)':>20}")
    sep = "═" * len(header)
    print(f"\n{sep}\n  MULTI-SEED RESULTS: {topo.upper()} | {scen.upper()} | {len(EVAL_SEEDS)} seeds\n{sep}\n{header}\n{sep}")
    for algo_name, runs in algo_runs.items():
        if not runs: continue
        accs = [r.acc_rate for r in runs]
        slas = [r.sla_rate for r in runs]
        lats = [r.avg_lat for r in runs]
        star = "★ " if "Ours" in algo_name else "  "
        print(f"  {star}{algo_name.replace('★ ',''):<26} | "
              f"{np.mean(accs):>6.1f} ± {np.std(accs):>4.1f}   | "
              f"{np.mean(slas):>8.2f} ± {np.std(slas):>5.2f}     | "
              f"{np.mean(lats):>6.2f} ± {np.std(lats):>4.2f} ms")
    print(sep)


def plot_multi_seed(algo_runs: dict, fig_dir: str, topo: str, scen: str):
    """Plot Rolling Acceptance with 95% CI shaded area."""
    os.makedirs(fig_dir, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    fig.suptitle(f"Multi-Seed Evaluation (95% CI) — {topo.upper()} | {scen.capitalize()}", fontsize=14, fontweight='bold')

    # ── Left: Rolling Acceptance with 95% CI ──
    ax1 = axes[0]
    for algo_name, runs in algo_runs.items():
        if not runs: continue
        rolling_arrays = [r.rolling_acceptance(500) for r in runs]
        min_len = min(len(a) for a in rolling_arrays)
        if min_len == 0: continue
        stacked = np.array([a[:min_len] for a in rolling_arrays])
        mean = np.mean(stacked, axis=0)
        std  = np.std(stacked, axis=0)
        ci   = 1.96 * std / np.sqrt(len(runs))
        color = get_color(runs[0])
        label = algo_name.replace("★ ", "")
        ax1.plot(mean, label=label, color=color, lw=2)
        ax1.fill_between(range(min_len), mean - ci, mean + ci, alpha=0.15, color=color)
    ax1.set_ylim(0, 110); ax1.set_xlabel("Step"); ax1.set_ylabel("Acceptance Rate (%)")
    ax1.set_title("Rolling Acceptance (window=500, 95% CI)"); ax1.legend(fontsize=9); ax1.grid(alpha=0.3)

    # ── Right: Bar chart Mean ± Std ──
    ax2 = axes[1]
    names, means, stds, colors = [], [], [], []
    for algo_name, runs in algo_runs.items():
        if not runs: continue
        names.append(algo_name.replace("★ ", ""))
        means.append(np.mean([r.sla_rate for r in runs]))
        stds.append(np.std([r.sla_rate for r in runs]))
        colors.append(get_color(runs[0]))
    bars = ax2.bar(names, means, yerr=stds, color=colors, alpha=0.85, capsize=5)
    ax2.bar_label(bars, fmt='%.2f%%', padding=3, fontsize=9)
    ax2.set_title("SLA Violation Rate (Mean ± Std)"); ax2.tick_params(axis='x', labelsize=8, rotation=15)

    fig.savefig(os.path.join(fig_dir, "multi_seed_ci.png"), dpi=200, bbox_inches='tight')
    fig.savefig(os.path.join(fig_dir, "multi_seed_ci.pdf"), dpi=200, bbox_inches='tight', format='pdf')
    plt.close(fig)
    logger.info(f"  ✅ Saved multi-seed figures → {fig_dir}")


def save_checkpoint(algo_runs: dict, fig_dir: str, topo: str, scen: str):
    """Save intermediate results as JSON checkpoint."""
    os.makedirs(fig_dir, exist_ok=True)
    checkpoint = {}
    for algo_name, runs in algo_runs.items():
        checkpoint[algo_name] = [{
            "seed": i, "acc": r.acc_rate, "sla": r.sla_rate,
            "avg_lat": r.avg_lat, "evac": r.evac_rate
        } for i, r in enumerate(runs)]
    path = os.path.join(fig_dir, "checkpoint.json")
    with open(path, "w") as f:
        json.dump(checkpoint, f, indent=2)
    logger.info(f"  💾 Checkpoint saved → {path}")


# ══════════════════════════════════════════════════════════════
#  Main — Multi-Seed Evaluation with 95% CI
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JO-VPPM v10 — Final Benchmark (Multi-Seed)")
    parser.add_argument("--topology", default="vietnam",
                        choices=["vietnam", "nsfnet", "geant2", "all"])
    parser.add_argument("--scenario", default="uniform",
                        choices=["uniform", "bursty", "heavy_tail", "all"])
    parser.add_argument("--steps",    default=10000, type=int,
                        help="Số request mỗi run (khuyến nghị 10000 cho Stress Test)")
    parser.add_argument("--skip-ilp", action="store_true",
                        help="Bỏ qua Exhaustive Search (rất chậm với GEANT2)")
    parser.add_argument("--single-seed", action="store_true",
                        help="Chỉ chạy 1 seed (SEED=42) để test nhanh")
    parser.add_argument("--load", default="stress",
                        choices=["normal", "stress"],
                        help="'normal'=arrival_rate 0.2, TTL(10,50) | 'stress'=arrival_rate 1.0, TTL(100,500)")
    parser.add_argument("--version", default="v10", help="Version của model để phân loại kết quả (v10, v9, v2,...)")
    args = parser.parse_args()

    # Load mode configuration
    if args.load == 'normal':
        ARRIVAL_RATE = 0.2
        TTL_RANGE = (10, 50)
        LOAD_LABEL = 'Normal'
    else:
        ARRIVAL_RATE = 1.0
        TTL_RANGE = (100, 500)
        LOAD_LABEL = 'Stress'

    BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_PATH  = os.path.join(BASE_DIR, 'data', 'processed', 'real_telecom_combined.csv')
    MDL_DIR    = os.path.join(BASE_DIR, 'results', 'models')
    FIG_ROOT   = os.path.join(BASE_DIR, 'results', 'figures')

    if not os.path.exists(DATA_PATH):
        DATA_PATH = os.path.join(BASE_DIR, 'data', 'real_telecom_combined.csv')

    seeds = [42] if args.single_seed else EVAL_SEEDS
    topologies = ["vietnam", "nsfnet", "geant2"] if args.topology == "all" else [args.topology]
    scenarios  = ["uniform", "bursty", "heavy_tail"] if args.scenario == "all" else [args.scenario]

    for topo_name in topologies:
        for scen in scenarios:
            logger.info(f"\n{'='*70}")
            logger.info(f"  TOPOLOGY: {topo_name.upper()} | SCENARIO: {scen.upper()} | "
                        f"LOAD: {LOAD_LABEL.upper()} | STEPS: {args.steps} | SEEDS: {len(seeds)}")
            logger.info(f"{'='*70}")

            def make_env(_topo=topo_name, _ar=ARRIVAL_RATE, _ttl=TTL_RANGE):
                env = JOVDPREnv(
                    repository=CSVRepository(DATA_PATH),
                    reward_calculator=RewardCalculator(lambda_latency=-50.0),
                    topology_manager=TopologyManager(_topo),
                    episode_length=args.steps
                )
                env.arrival_rate = _ar
                env.ttl_range = _ttl
                return env

            mdl_path  = os.path.join(MDL_DIR, args.version, f"dgrl_{args.version}_final_{topo_name}.zip")
            norm_path = os.path.join(MDL_DIR, args.version, f"vec_normalize_{args.version}_{topo_name}.pkl")

            fig_dir   = os.path.join(FIG_ROOT, args.version, f"benchmark_{topo_name}_{scen}_{args.load}")
            skip_ilp  = args.skip_ilp or (topo_name == 'geant2' and args.steps > 1000)

            algo_runs = {
                "Exhaustive Pair-Search": [],
                "Traditional Greedy": [],
                "Decoupled AI": [],
                "★ JO-VPPM v10 (Ours)": [],
            }

            for si, seed in enumerate(seeds):
                logger.info(f"\n  ── Seed {si+1}/{len(seeds)}: {seed} ──")

                if not skip_ilp:
                    logger.info(f"    [1/4] Exhaustive Pair-Search (seed={seed})...")
                    algo_runs["Exhaustive Pair-Search"].append(
                        run_exhaustive_search(make_env, scen, args.steps, seed))

                logger.info(f"    [2/4] Traditional Greedy (seed={seed})...")
                algo_runs["Traditional Greedy"].append(
                    run_traditional_greedy(make_env, scen, args.steps, seed))

                logger.info(f"    [3/4] Decoupled AI (seed={seed})...")
                algo_runs["Decoupled AI"].append(
                    run_decoupled(make_env, scen, args.steps, seed))

                logger.info(f"    [4/4] JO-VPPM v10 (seed={seed})...")
                algo_runs["★ JO-VPPM v10 (Ours)"].append(
                    run_jo_vppm(make_env, mdl_path, norm_path, scen, args.steps, seed, label="★ JO-VPPM v10 (Ours)"))

                # Checkpoint after each seed
                save_checkpoint(algo_runs, fig_dir, topo_name, scen)

            # Plot single-seed dashboard (first seed) for backward compat
            first_seed_results = []
            for algo_name, runs in algo_runs.items():
                if runs:
                    runs[0].topology = topo_name
                    first_seed_results.append(runs[0])
            if first_seed_results:
                plot_scenario(first_seed_results, fig_dir)

            # Plot multi-seed CI figure
            if len(seeds) > 1:
                plot_multi_seed(algo_runs, fig_dir, topo_name, scen)

            # Print multi-seed summary
            print_multi_seed_table(algo_runs, topo_name, scen)
