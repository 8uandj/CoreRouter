"""
train_dgrl.py — Huấn luyện PPO với kiến trúc DGRL (Graph Attention Network)

Nâng cấp từ MLP thuần (Phase 3) → GNN Policy (Phase 4):
  - Agent nhìn thấy cấu trúc TOPOLOGY, không chỉ các con số rời rạc.
  - GAT multi-head attention tự phát hiện node quan trọng/lân cận.
  - Kỳ vọng: Acceptance Ratio tăng từ ~62% lên >75%.
"""

import os
import sys
import logging

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import (
    CheckpointCallback, EvalCallback, BaseCallback
)

from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("DGRL-Trainer")


class LinearLRDecay(BaseCallback):
    """Linear Learning Rate Decay từ initial_lr → final_lr."""
    def __init__(self, total_timesteps: int, initial_lr=3e-4, final_lr=5e-5):
        super().__init__()
        self.total_ts   = total_timesteps
        self.initial_lr = initial_lr
        self.final_lr   = final_lr

    def _on_step(self) -> bool:
        progress = self.num_timesteps / self.total_ts
        lr = self.initial_lr - progress * (self.initial_lr - self.final_lr)
        self.model.policy.optimizer.param_groups[0]['lr'] = lr
        return True


def build_env(root_dir: str) -> JOVDPREnv:
    data_path = os.path.join(root_dir, 'data', 'real_telecom_combined.csv')
    repo = CSVRepository(data_path)
    logger.info(f"Dataset loaded: {len(repo.dataset)} flows from {data_path}")
    return JOVDPREnv(
        repository=repo,
        reward_calculator=RewardCalculator(),
        num_nodes=5,
        episode_length=100
    )


def main():
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    log_dir  = os.path.join(root_dir, 'results', 'logs', 'dgrl_hyper')
    ckpt_dir = os.path.join(log_dir, 'checkpoints')
    best_dir = os.path.join(log_dir, 'best_model')
    model_path = os.path.join(root_dir, 'results', 'models', 'dgrl_hyper_jo_vdpr.zip')
    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(best_dir, exist_ok=True)

    print("=" * 65)
    print("  JO-VDPR DGRL — Deep Graph Reinforcement Learning (Phase 5 - Hyper)")
    print("  Kiến trúc: Graph Attention Network → Actor-Critic (PPO)")
    print("  Cải tiến: Phạt nặng MSD violation, Tăng thời gian Exploration.")
    print("=" * 65)

    # ── Môi trường ──
    train_env = Monitor(build_env(root_dir), log_dir)
    eval_env  = build_env(root_dir)

    # ── Callbacks ──
    TOTAL = 2_000_000  # Phase 5: Train cực sâu

    checkpoint_cb = CheckpointCallback(
        save_freq=200_000,
        save_path=ckpt_dir,
        name_prefix="dgrl_hyper_ckpt"
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=best_dir,
        log_path=os.path.join(log_dir, 'eval'),
        eval_freq=50_000,
        n_eval_episodes=100, # Đánh giá thật kĩ 
        deterministic=True,
        verbose=1
    )
    # Học chậm lại để không trật bánh ở cuối (3e-4 -> 1e-5)
    lr_cb = LinearLRDecay(TOTAL, initial_lr=3e-4, final_lr=1e-5)

    # ── Build Model ──
    model = PPO(
        policy=GNNActorCriticPolicy,
        env=train_env,
        verbose=1,
        n_steps=2048,
        batch_size=128,         # Tăng batch size để gradient ổn định hơn
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.05,          # TĂNG ENTROPY: Bắt AI phá kén Greedy (vốn là 0.02)
        vf_coef=0.5,
        max_grad_norm=0.5,
        learning_rate=3e-4,
        tensorboard_log=log_dir,
        policy_kwargs=dict(
            num_nodes=5,
            gat_hidden=64,
            gat_heads=4,
            features_dim=256,
        )
    )

    param_count = sum(p.numel() for p in model.policy.parameters() if p.requires_grad)
    logger.info(f"Số tham số GNN Policy: {param_count:,}")
    logger.info(f"Bắt đầu huấn luyện cường độ cao {TOTAL:,} timesteps...")

    model.learn(
        total_timesteps=TOTAL,
        callback=[checkpoint_cb, eval_cb, lr_cb],
        reset_num_timesteps=True
    )

    model.save(model_path)
    logger.info(f"Model DGRL Hyper đã lưu tại: {model_path}")
    print(f"\n✅ Training DGRL Hyper hoàn tất! Model: {model_path}")


if __name__ == "__main__":
    main()
