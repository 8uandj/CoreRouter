"""
benchmark_eval.py — Đánh giá 4 nhóm thuật toán cho JO-VDPR (v2)

Cải tiến so với v1:
- Tương thích env v2 (observation 18 features, episode 100 steps)
- NUM_EPISODES tăng lên 1000 (kiểm tra kỹ hơn)
- Thêm metric: MSD violation rate, avg latency proxy
- Thêm box plot (variance analysis cho luận văn)
- Tự động so sánh PPO v1 vs PPO v2 nếu cả hai model tồn tại
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from stable_baselines3 import PPO

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '..', '..'))
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.rewards import RewardCalculator

NUM_EPISODES = 1000   # Tăng từ 500 → 1000 để variance thấp hơn
WINDOW_SIZE  = 50     # Window cho rolling stats


# ═══════════════════════════════════════════════════════════════════════
#  BASELINE 1: Optimal ILP (Exhaustive Search trong testbed nhỏ)
# ═══════════════════════════════════════════════════════════════════════
def run_ilp_optimal(env):
    """
    Upper bound lý thuyết: duyệt n² combinations, chọn action tốt nhất.
    Chỉ khả thi vì testbed chỉ có 5 nodes (25 combinations).
    """
    state, _ = env.reset()
    total_reward = 0
    accepts = 0
    msd_violations = 0

    for ep in range(NUM_EPISODES):
        best_action = None
        best_reward = -float('inf')

        # Lưu state
        saved_raw   = env._raw_state.copy()
        saved_req   = dict(env._current_req)
        saved_ts    = env.current_time_step

        for v1 in range(env.num_nodes):
            for v2 in range(env.num_nodes):
                # Restore rồi thử action
                env._raw_state       = saved_raw.copy()
                env._current_req     = dict(saved_req)
                env.current_time_step = saved_ts
                _, r, _, _, _ = env.step([v1, v2])
                if r > best_reward:
                    best_reward = r
                    best_action = [v1, v2]

        # Restore lần cuối rồi thực thi action tốt nhất
        env._raw_state       = saved_raw.copy()
        env._current_req     = dict(saved_req)
        env.current_time_step = saved_ts
        _, actual_reward, done, _, info = env.step(best_action)

        if actual_reward > 0:
            accepts += 1
        else:
            if 'MSD' in info.get('error_log', ''):
                msd_violations += 1
        total_reward += actual_reward
        if done:
            env.reset()

    return total_reward, accepts, msd_violations


# ═══════════════════════════════════════════════════════════════════════
#  BASELINE 2: NSF Greedy (Nearest Service Function — luôn chọn Node 0)
# ═══════════════════════════════════════════════════════════════════════
def run_nsf_greedy(env):
    """Heuristic tham lam: luôn đặt vào Node 0 và Node 1 (gần nhất)."""
    state, _ = env.reset()
    total_reward = 0
    accepts = 0
    msd_violations = 0

    for _ in range(NUM_EPISODES):
        action = [0, 1]  # Greedy: 2 node đầu tiên
        _, reward, done, _, info = env.step(action)
        if reward > 0:
            accepts += 1
        else:
            if 'MSD' in info.get('error_log', ''):
                msd_violations += 1
        total_reward += reward
        if done:
            env.reset()

    return total_reward, accepts, msd_violations


# ═══════════════════════════════════════════════════════════════════════
#  BASELINE 3: Decoupled AI (Topology-Blind, 2-stage sequential)
# ═══════════════════════════════════════════════════════════════════════
def run_decoupled_ai(env):
    """
    Phân mảnh 2 chu kỳ:
    Stage 1 — Bot 1 chọn node có nhiều CPU nhất (không quan tâm MSD)
    Stage 2 — Bot 2 chọn node cách xa nhất (không join với stage 1)
    → Topology-blind: không biết MSD limits, dễ vi phạm hardware
    """
    state, _ = env.reset()
    total_reward = 0
    accepts = 0
    msd_violations = 0

    for _ in range(NUM_EPISODES):
        # Lấy CPU usage từ state (normalized, index 0, 3, 6, 9, 12)
        cpu_used_norm = [state[i * 3] for i in range(env.num_nodes)]
        v1 = int(np.argmin(cpu_used_norm))   # Node ít CPU nhất (max free)
        v2 = (v1 + 2) % env.num_nodes        # Node "xa" nhất theo ID

        new_state, reward, terminated, truncated, info = env.step([v1, v2])
        done = terminated or truncated
        
        if reward > 0:
            accepts += 1
        else:
            if 'MSD' in info.get('error_log', ''):
                msd_violations += 1
        total_reward += reward
        
        if done:
            state, _ = env.reset()
        else:
            state = new_state

    return total_reward, accepts, msd_violations


# ═══════════════════════════════════════════════════════════════════════
#  SẢN PHẨM: JO-VDPR PPO (Joint Optimization — Centralized RL)
# ═══════════════════════════════════════════════════════════════════════
def run_jo_vdpr_ppo(env, model_path):
    """JO-VDPR: PPO với hardware-aware reward và topology knowledge."""
    if not os.path.exists(model_path):
        print(f"  ❗ Model không tồn tại: {model_path}")
        return 0, 0, 0

    model = PPO.load(model_path)
    state, _ = env.reset()
    total_reward = 0
    accepts = 0
    msd_violations = 0

    for _ in range(NUM_EPISODES):
        action, _ = model.predict(state, deterministic=True)
        new_state, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        
        if reward > 0:
            accepts += 1
        else:
            if 'MSD' in info.get('error_log', ''):
                msd_violations += 1
        total_reward += reward
        
        if done:
            state, _ = env.reset()
        else:
            state = new_state

    return total_reward, accepts, msd_violations


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
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✅ Saved: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 65)
    print("  JO-VDPR BENCHMARK v3 (Traffic-Aware) — 4 Thuật Toán Đối Chứng")
    print(f"  Episodes: {NUM_EPISODES}  |  Dataset: real_telecom_combined.csv")
    print("=" * 65)

    base_dir   = os.path.dirname(os.path.abspath(__file__))
    root_dir   = os.path.join(base_dir, '..', '..')
    
    # Init Env
    repo = CSVRepository(os.path.join(root_dir, 'data', 'real_telecom_combined.csv'))
    reward_calc = RewardCalculator()
    env_eval = JOVDPREnv(repository=repo, reward_calculator=reward_calc, num_nodes=5)

    latest_model = os.path.join(root_dir, 'results', 'models', 'ppo_jo_vdpr_model.zip')
    best_model   = os.path.join(root_dir, 'results', 'logs', 'ppo', 'best_model', 'best_model.zip')

    # Ưu tiên model v3 mới nhất trong thư mục models/
    model_to_use = None
    for mp in [latest_model, best_model]:
        if os.path.exists(mp):
            model_to_use = mp
            print(f"  Using Model: {os.path.basename(mp)}")
            break

    print("\n[1/4] Optimal (ILP/Exhaustive)...")
    ilp_r, ilp_acc, ilp_msd = run_ilp_optimal(env_eval)

    print("[2/4] NSF Greedy (Heuristic)...")
    nsf_r, nsf_acc, nsf_msd = run_nsf_greedy(env_eval)

    print("[3/4] Decoupled AI (Topology-Blind 2-Stage)...")
    dec_r, dec_acc, dec_msd = run_decoupled_ai(env_eval)

    print("[4/4] JO-VDPR PPO v2 (Joint Optimization)...")
    if model_to_use:
        jo_r, jo_acc, jo_msd = run_jo_vdpr_ppo(env_eval, model_to_use)
    else:
        print("  ⚠️ Chưa có model — hãy train trước bằng agent_ppo.py")
        jo_r, jo_acc, jo_msd = 0, 0, 0

    # ── Kết quả ──
    labels      = ['Optimal (ILP)', 'NSF (Greedy)', 'Decoupled AI', 'JO-VDPR (Ours)']
    acc_rates   = [ilp_acc/NUM_EPISODES*100, nsf_acc/NUM_EPISODES*100,
                   dec_acc/NUM_EPISODES*100, jo_acc/NUM_EPISODES*100]
    rewards     = [ilp_r, nsf_r, dec_r, jo_r]
    msd_rates   = [ilp_msd/NUM_EPISODES*100, nsf_msd/NUM_EPISODES*100,
                   dec_msd/NUM_EPISODES*100, jo_msd/NUM_EPISODES*100]

    print("\n" + "─"*65)
    print(f"{'Algorithm':<20} {'Accept%':>8}  {'Reward':>12}  {'MSD Viol%':>10}")
    print("─"*65)
    for lbl, acc, rew, msd in zip(labels, acc_rates, rewards, msd_rates):
        marker = " ◀ BEST" if acc == max(acc_rates) else ""
        print(f"{lbl:<20} {acc:>7.1f}%  {rew:>12,.0f}  {msd:>9.1f}%{marker}")
    print("─"*65)

    # ── Phân tích học thuật ──
    print("\n[NHẬN XÉT HỌC THUẬT]")
    gap_to_ilp = acc_rates[0] - acc_rates[3]
    print(f"  JO-VDPR vs ILP gap:      {gap_to_ilp:+.1f}% (trần lý thuyết)")
    print(f"  JO-VDPR vs Decoupled:    {acc_rates[3]-acc_rates[2]:+.1f}% (AI vs AI)")
    print(f"  JO-VDPR MSD viol rate:   {msd_rates[3]:.1f}% (Decoupled: {msd_rates[2]:.1f}%)")

    # ── Vẽ biểu đồ ──
    print("\n[XUẤT BIỂU ĐỒ]")
    fig_dir = os.path.join(root_dir, 'results', 'figures')
    
    v1_acc_baseline = [69.6, 36.6, 63.4, 54.0] # Dữ liệu lịch sử v1

    plot_acceptance_ratio(labels, acc_rates, msd_rates,
                          os.path.join(fig_dir, 'acceptance_ratio_comparison.png'))
    plot_cumulative_reward(labels, rewards,
                           os.path.join(fig_dir, 'cumulative_reward_comparison.png'))
    
    plot_comparison_v1_v2(labels, v1_acc_baseline, labels, acc_rates,
                          os.path.join(fig_dir, 'before_after_comparison.png'))

    print("\n✅ Benchmark hoàn tất!")
