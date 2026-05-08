"""
train.py — JO-VDPR DGRL Training (Phase 8 — MaskablePPO)

Bốn cải tiến cốt lõi so với Phase 7:
  1. MaskablePPO: Invalid Action Masking — loại bỏ 100%% xác suất chọn node hết tài nguyên
  2. Proportional Knapsack Reward — thưởng phân biệt SFC nặng / nhẹ để Agent học chiến lược dài hạn
  3. Static Adjacency (giữ lại từ Phase 7)
  4. Adaptive Penalty Callback (giữ lại từ Phase 7)

Lịch sử các version:
    train_mlp_v1.py     — Phase 1-3 (MLP PPO, 500K steps)
    train_dgrl_v4.py    — Phase 4   (GNN Static Adj, 1M steps, 5 nodes)
    train_dgrl_v5.py    — Phase 5   (GNN Hyper, 2M steps, 5 nodes)
    train_dgrl_v6.py    — Phase 6   (Dynamic Adj — BUG, đã dừng)
    train.py v7         — Phase 7   (Static Adj + Adaptive λ, 10 nodes, PPO)
    train.py (this)     — Phase 8   (MaskablePPO + Knapsack Reward)
"""

import os
import sys
import logging
import numpy as np

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from stable_baselines3.common.vec_env    import SubprocVecEnv, VecMonitor, VecNormalize, DummyVecEnv
from stable_baselines3.common.monitor    import Monitor
from stable_baselines3.common.utils      import set_random_seed
from stable_baselines3.common.callbacks import (
    CheckpointCallback, BaseCallback, CallbackList
)

from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env       import JOVDPREnv
from src.orchestration.jo_vdpr.rewards   import RewardCalculator
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.orchestration.jo_vdpr.topology  import NUM_NODES

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("DGRL-v8")


# ── Hyperparameters ──────────────────────────────────────────
N_ENVS = 10
N_STEPS = 512       # [NEW] 10 * 512 = 5120 steps per rollout
BATCH_SIZE = 256    # [NEW] 5120 / 256 = 20 mini-batches
TOTAL_STEPS = 2_000_000

def linear_schedule(initial_value: float, final_value: float = 0.0):
    """Lịch trình giảm tuyến tính/phi tuyến cho các siêu tham số."""
    def func(progress_remaining: float) -> float:
        return final_value + progress_remaining * (initial_value - final_value)
    return func


class EntropyDecayCallback(BaseCallback):
    """Giảm ent_coef tuyến tính từ initial_value → final_value trong suốt quá trình train."""
    def __init__(self, initial: float = 0.01, final: float = 0.0001, total_steps: int = 2_000_000):
        super().__init__()
        self.initial     = initial
        self.final       = final
        self.total_steps = total_steps

    def _on_step(self) -> bool:
        progress = self.num_timesteps / self.total_steps
        new_ent  = self.final + (1.0 - progress) * (self.initial - self.final)
        self.model.ent_coef = float(new_ent)
        return True


class AdaptivePenaltyCallback(BaseCallback):
    """
    Tự động điều chỉnh lambda_latency trong RewardCalculator để tối ưu SLA.
    """
    def __init__(self,
                  reward_calculator: RewardCalculator,
                  target_rate:       float = 0.05,    # Mục tiêu: < 5% SLA violations
                  update_freq:       int   = 5120,   # Cập nhật mỗi rollout (10*512)
                  lr_lambda:         float = 5.0,    # Bước học của λ
                  lambda_min:        float = -2000.0,
                  lambda_max:        float = -5.0,
                  verbose:           int   = 1):
        super().__init__(verbose=verbose)
        self.reward_calc  = reward_calculator
        self.target_rate  = target_rate
        self.update_freq  = update_freq
        self.lr_lambda    = lr_lambda
        self.lambda_min   = lambda_min
        self.lambda_max   = lambda_max
        self._viol_buffer = []

    def _on_step(self) -> bool:
        if self.locals.get('infos'):
            for info in self.locals['infos']:
                vr = info.get('latency_violation_rate', 0.0)
                self._viol_buffer.append(vr)

        if self.num_timesteps % self.update_freq == 0 and self._viol_buffer:
            current_rate = float(np.mean(self._viol_buffer))
            self._viol_buffer.clear()

            old_lambda = self.reward_calc.lambda_latency
            # Lagrangian Update: nếu vi phạm nhiều -> tăng phạt (λ âm hơn)
            delta      = self.lr_lambda * (current_rate - self.target_rate)
            new_lambda = old_lambda - delta
            new_lambda = float(np.clip(new_lambda, self.lambda_min, self.lambda_max))

            self.reward_calc.update_lambda_latency(new_lambda)

            try:
                self.training_env.env_method("update_reward_lambda", new_lambda)
            except Exception:
                pass

            if self.verbose >= 1:
                logger.info(
                    f"[AdaptivePenalty] step={self.num_timesteps:,} | "
                    f"viol_rate={current_rate:.3f} (target={self.target_rate}) | "
                    f"λ_latency: {old_lambda:.1f} → {new_lambda:.1f}"
                )
        return True


# ═══════════════════════════════════════════════════════════════
#  Env factory for Multiprocessing
# ═══════════════════════════════════════════════════════════════
def make_env(root_dir: str, reward_calc: RewardCalculator, rank: int, seed: int = 0):
    """
    Utility function for multiprocessed env.
    """
    def _init():
        import torch
        torch.set_num_threads(1)  # Khủng khoảng nghẽn cổ chai: ép mỗi process chạy 1 thread
        data_path = os.path.join(root_dir, 'data', 'real_telecom_combined.csv')
        repo = CSVRepository(data_path)
        env = JOVDPREnv(
            repository=repo,
            reward_calculator=reward_calc,
            num_nodes=NUM_NODES,
            episode_length=100
        )
        env.reset(seed=seed + rank)
        return env
    set_random_seed(seed)
    return _init


def build_eval_env(root_dir: str, reward_calc: RewardCalculator) -> JOVDPREnv:
    data_path = os.path.join(root_dir, 'data', 'real_telecom_combined.csv')
    repo = CSVRepository(data_path)
    return JOVDPREnv(
        repository=repo,
        reward_calculator=reward_calc,
        num_nodes=NUM_NODES,
        episode_length=100
    )


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════
def main():
    root_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    log_dir   = os.path.join(root_dir, 'results', 'logs',   'dgrl_v8')
    ckpt_dir  = os.path.join(log_dir, 'checkpoints')
    best_dir  = os.path.join(log_dir, 'best_model')
    model_out = os.path.join(root_dir, 'results', 'models', 'dgrl_v8.zip')
    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(best_dir,  exist_ok=True)

    print("=" * 72)
    print("  JO-VDPR DGRL Phase 8.3 — The Optimized Orchestrator")
    print("  Topology  : 10 DC Nodes (Hà Nội → Cần Thơ, latency địa lý thực)")
    print("  GNN       : Static Adjacency + LayerNorm + Dropout (v3 Policy)")
    print("  Reward    : Adaptive λ_latency + Vector Normalization + Knapsack")
    print("  Masking   : action_masks() lọc bỏ hard constraints (MSD/CPU)")
    print("=" * 72)

    # ── Configurations ─────────────────────────────────────────
    reward_calc = RewardCalculator(lambda_latency=-20.0, knapsack_scale=0.5)

    # ── Môi trường huấn luyện (10 envs) ─────────────────────────
    train_env = SubprocVecEnv([
        make_env(root_dir, reward_calc, i) for i in range(N_ENVS)
    ])
    train_env = VecMonitor(train_env, log_dir)
    # [IMPORTANT] VecNormalize — Ổn định hóa Reward và Observation
    train_env = VecNormalize(train_env, norm_obs=True, norm_reward=True, clip_reward=10.0)

    # ── Môi trường đánh giá (Phải khớp cấu trúc Wrapper với Train) ──
    eval_raw = build_eval_env(root_dir, RewardCalculator(lambda_latency=-20.0, knapsack_scale=0.5))
    eval_env = DummyVecEnv([lambda: eval_raw])
    eval_env = VecMonitor(eval_env) # [FIX] Thêm Monitor để khớp với Train
    # Không update stats trong lúc eval, dùng chung stats của train_env
    eval_env = VecNormalize(eval_env, norm_obs=True, norm_reward=False, training=False)

    ckpt_cb = CheckpointCallback(
        save_freq=max(1000, 20_000 // N_ENVS), 
        save_path=ckpt_dir, 
        name_prefix='dgrl_v8_ckpt'
    )
    eval_cb = MaskableEvalCallback(
        eval_env,
        best_model_save_path=best_dir,
        log_path=os.path.join(log_dir, 'eval'),
        eval_freq=max(2000, 50_000 // N_ENVS),
        n_eval_episodes=50,
        deterministic=True,
        verbose=1
    )
    adp_cb = AdaptivePenaltyCallback(reward_calc, target_rate=0.05)

    entropy_cb = EntropyDecayCallback(initial=0.01, final=0.0001, total_steps=TOTAL_STEPS)

    callbacks = CallbackList([
        ckpt_cb, eval_cb, adp_cb,
        entropy_cb
    ])

    # ── Model ───────────────────────────────────────────────────
    model = MaskablePPO(
        policy=GNNActorCriticPolicy,
        env=train_env,
        verbose=1,
        n_steps=N_STEPS,
        batch_size=BATCH_SIZE,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,         # Bắt đầu ở 0.01, EntropyDecayCallback sẽ giảm dần
        vf_coef=0.7,           # Tập trung học giá trị Critic
        max_grad_norm=0.5,
        learning_rate=3e-4,    # LinearLRDecay callback sẽ giảm dần
        tensorboard_log=log_dir,
        policy_kwargs=dict(
            num_nodes=NUM_NODES,
            gat_hidden=64,
            gat_heads=4,
            features_dim=256,
        )
    )

    logger.info(f"Training {TOTAL_STEPS:,} timesteps (Phase 8.3)...")

    model.learn(
        total_timesteps=TOTAL_STEPS,
        callback=callbacks,
        reset_num_timesteps=True
    )

    model.save(model_out)
    logger.info(f"✅ Model Phase 8 (MaskablePPO) saved: {model_out}")
    print(f"\n🎉 Training DGRL v8 complete! Model: {model_out}")


if __name__ == '__main__':
    main()
