"""
train_v9.py — JO-VDPR DGRL Training Phase 9 (Warm-Start từ dgrl_v8)

Chiến lược:
    - WARM-START: Load dgrl_v8.zip rồi tiếp tục train thêm 1,500,000 steps
      thay vì train lại từ đầu (tiết kiệm ~8-12 giờ CPU/GPU).
    - Model mới dùng env v5 với Physics-Aware Latency (SRv6 overhead + M/M/1).
    - Observation Space thay đổi: 48 → 53 dims → PHẢI tạo model mới từ đầu.
      (Warm-start chỉ áp dụng khi obs space giữ nguyên; vì đây là model mới
       với GNN v4, chúng ta train 1.5M steps đủ để hội tụ từ đầu.)
    
    [NOTE] Nếu có Kaggle GPU (P100/T4): 1.5M steps × 10 envs ≈ 2-3 giờ.
           Nếu chỉ CPU: ~12-18 giờ → khuyến nghị chạy qua đêm.

Cải tiến so với Phase 8:
    1. Physics-Aware Latency: SRv6 overhead + M/M/1 queuing
    2. Observation +5 dims: global context (avg_cpu, avg_msd, req_intensity...)
    3. LATENCY_THRESHOLDS chặt hơn (IoT: 10ms, Video: 20ms, VoIP: 30ms)
    4. Entopy Decay mạnh hơn: 0.02 → 0.00005 (khuyến khích khai thác hơn)
    5. lambda_latency ban đầu = -50 (phạt SLA mạnh hơn từ đầu)
"""

import os
import sys
import logging
import numpy as np

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor, VecNormalize, DummyVecEnv
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback, CallbackList

from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env     import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.orchestration.jo_vdpr.topology import NUM_NODES

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("DGRL-v9")


# ── Hyperparameters ──────────────────────────────────────────
N_ENVS       = 10
N_STEPS      = 512
BATCH_SIZE   = 256
TOTAL_STEPS  = 1_500_000   # Đủ cho Phase 9 (model mới, obs thay đổi)
LEARNING_RATE = 2e-4       # Hơi thấp hơn v8 (3e-4) để ổn định hơn


# ─────────────────────────────────────────────────────────────
#  Callbacks
# ─────────────────────────────────────────────────────────────
class EntropyDecayCallback(BaseCallback):
    """Giảm ent_coef phi tuyến: nhanh lúc đầu, chậm về sau."""
    def __init__(self, initial: float = 0.02, final: float = 0.00005,
                 total_steps: int = TOTAL_STEPS):
        super().__init__()
        self.initial     = initial
        self.final       = final
        self.total_steps = total_steps

    def _on_step(self) -> bool:
        progress = self.num_timesteps / self.total_steps
        # Cosine annealing: ổn định hơn linear
        new_ent = self.final + 0.5 * (self.initial - self.final) * (
            1 + np.cos(np.pi * progress)
        )
        self.model.ent_coef = float(new_ent)
        return True


class AdaptivePenaltyCallback(BaseCallback):
    """
    Tự động điều chỉnh lambda_latency để tối ưu SLA Compliance.
    Mục tiêu: < 3% SLA violation (chặt hơn Phase 8's 5%)
    """
    def __init__(self,
                 reward_calculator: RewardCalculator,
                 target_rate: float = 0.03,    # <3% SLA violation
                 update_freq: int   = 5120,
                 lr_lambda:   float = 8.0,     # Tốc độ cập nhật lambda nhanh hơn
                 lambda_min:  float = -3000.0,
                 lambda_max:  float = -5.0,
                 verbose:     int   = 1):
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
            delta      = self.lr_lambda * (current_rate - self.target_rate)
            new_lambda = float(np.clip(old_lambda - delta, self.lambda_min, self.lambda_max))
            self.reward_calc.update_lambda_latency(new_lambda)

            try:
                self.training_env.env_method("update_reward_lambda", new_lambda)
            except Exception:
                pass

            if self.verbose >= 1:
                logger.info(
                    f"[AdaptivePenalty] step={self.num_timesteps:,} | "
                    f"viol_rate={current_rate:.3f} (target={self.target_rate}) | "
                    f"λ: {old_lambda:.1f} → {new_lambda:.1f}"
                )
        return True


# ─────────────────────────────────────────────────────────────
#  Env factory
# ─────────────────────────────────────────────────────────────
def make_env(root_dir: str, reward_calc: RewardCalculator, rank: int, seed: int = 0):
    def _init():
        import torch
        torch.set_num_threads(1)
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


# ─────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────
def main():
    root_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    log_dir   = os.path.join(root_dir, 'results', 'logs', 'dgrl_v9')
    ckpt_dir  = os.path.join(log_dir, 'checkpoints')
    best_dir  = os.path.join(log_dir, 'best_model')
    model_out = os.path.join(root_dir, 'results', 'models', 'dgrl_v9.zip')
    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(best_dir, exist_ok=True)

    print("=" * 76)
    print("  JO-VDPR DGRL Phase 9 — Physics-Aware Latency + Global Context GNN")
    print("  Topology  : 10 DC Nodes (Hà Nội → Cần Thơ, Haversine geodesic)")
    print("  Latency   : 4-component model: D_prop + D_srv6 + D_queue_v1 + D_queue_v2")
    print("  GNN       : GAT v4 + Global Context Encoder (53-dim obs)")
    print("  Reward    : Adaptive λ (target 3% SLA viol) + Knapsack + Cosine entropy")
    print(f"  Training  : {TOTAL_STEPS:,} steps × {N_ENVS} envs = {TOTAL_STEPS * N_ENVS:,} total sims")
    print("=" * 76)

    # ── Configurations ──────────────────────────────────────
    # lambda_latency=-50: phạt SLA mạnh hơn ngay từ đầu so với v8 (-20)
    reward_calc = RewardCalculator(lambda_latency=-50.0, knapsack_scale=0.5)

    # ── Training envs ────────────────────────────────────────
    train_env = SubprocVecEnv([
        make_env(root_dir, reward_calc, i) for i in range(N_ENVS)
    ])
    train_env = VecMonitor(train_env, log_dir)
    train_env = VecNormalize(train_env, norm_obs=True, norm_reward=True, clip_reward=10.0)

    # ── Eval env ─────────────────────────────────────────────
    eval_raw  = build_eval_env(root_dir, RewardCalculator(lambda_latency=-50.0, knapsack_scale=0.5))
    eval_env  = DummyVecEnv([lambda: eval_raw])
    eval_env  = VecMonitor(eval_env)
    eval_env  = VecNormalize(eval_env, norm_obs=True, norm_reward=False, training=False)

    # ── Callbacks ────────────────────────────────────────────
    ckpt_cb = CheckpointCallback(
        save_freq=max(1000, 15_000 // N_ENVS),
        save_path=ckpt_dir,
        name_prefix='dgrl_v9_ckpt'
    )
    eval_cb = MaskableEvalCallback(
        eval_env,
        best_model_save_path=best_dir,
        log_path=os.path.join(log_dir, 'eval'),
        eval_freq=max(2000, 40_000 // N_ENVS),
        n_eval_episodes=50,
        deterministic=True,
        verbose=1
    )
    adp_cb     = AdaptivePenaltyCallback(reward_calc, target_rate=0.03)
    entropy_cb = EntropyDecayCallback(initial=0.02, final=0.00005, total_steps=TOTAL_STEPS)

    callbacks = CallbackList([ckpt_cb, eval_cb, adp_cb, entropy_cb])

    # ── Model ────────────────────────────────────────────────
    # Phase 9 phải tạo model MỚI (obs space 48 → 53 không tương thích)
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
        ent_coef=0.02,         # Cao hơn v8 (0.01), cosine decay sẽ giảm dần
        vf_coef=0.7,
        max_grad_norm=0.5,
        learning_rate=LEARNING_RATE,
        tensorboard_log=log_dir,
        policy_kwargs=dict(
            num_nodes=NUM_NODES,
            gat_hidden=64,
            gat_heads=4,
            features_dim=256,
        )
    )

    logger.info(f"Training {TOTAL_STEPS:,} timesteps (Phase 9)...")
    logger.info(f"Obs space: {model.observation_space.shape[0]} dims")
    logger.info(f"Action space: {model.action_space}")

    model.learn(
        total_timesteps=TOTAL_STEPS,
        callback=callbacks,
        reset_num_timesteps=True
    )

    model.save(model_out)
    logger.info(f"✅ Model Phase 9 saved: {model_out}")
    print(f"\n🎉 Training dgrl_v9 complete! Model: {model_out}")


if __name__ == '__main__':
    main()
