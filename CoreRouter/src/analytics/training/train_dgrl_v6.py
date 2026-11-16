"""
train.py — JO-VDPR DGRL Training Script (Phase 6 — Canonical)

Đây là file training chính thức duy nhất từ Phase 6 trở đi.
Các phiên bản cũ được lưu tại:
    train_mlp_v1.py      — Phase 1-3 (MLP PPO, 500K steps)
    train_dgrl_v4.py     — Phase 4   (GNN, Static Adj, 1M steps)
    train_dgrl_v5.py     — Phase 5   (GNN, Hyper, 2M steps)

Cải tiến Phase 6:
    - Topology 10 nodes thực tế (Hà Nội 🡒 Cần Thơ, latency địa lý)
    - MSD-Aware Dynamic Adjacency (GNN tự né node hết MSD)
    - 4 features/node (+ msd_free_ratio)
    - Residual skip-connection trong GAT
    - EntCoef = 0.03 (cân bằng Explore/Exploit)
    - BatchSize = 256 (gradient mượt hơn)
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
from src.orchestration.jo_vdpr.topology import NUM_NODES

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("DGRL-v6")


class LinearLRDecay(BaseCallback):
    """Linear LR decay từ initial_lr → final_lr trong suốt quá trình train."""
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
    logger.info(f"Dataset: {len(repo.dataset)} flows từ {data_path}")
    return JOVDPREnv(
        repository=repo,
        reward_calculator=RewardCalculator(),
        num_nodes=NUM_NODES,    # 10 nodes (từ topology.py)
        episode_length=100
    )


def main():
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    log_dir  = os.path.join(root_dir, 'results', 'logs', 'dgrl_v6')
    ckpt_dir = os.path.join(log_dir, 'checkpoints')
    best_dir = os.path.join(log_dir, 'best_model')
    model_out = os.path.join(root_dir, 'results', 'models', 'dgrl_v6.zip')

    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(best_dir,  exist_ok=True)

    print("=" * 70)
    print("  JO-VDPR DGRL Phase 6 — MSD-Aware Dynamic GNN")
    print("  Topology: 10 DC Nodes (Hà Nội → Cần Thơ, latency địa lý thực)")
    print("  GNN: Dynamic Adjacency + Residual Skip-Connection")
    print("=" * 70)

    train_env = Monitor(build_env(root_dir), log_dir)
    eval_env  = build_env(root_dir)

    TOTAL = 2_000_000

    checkpoint_cb = CheckpointCallback(
        save_freq=200_000,
        save_path=ckpt_dir,
        name_prefix='dgrl_v6_ckpt'
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=best_dir,
        log_path=os.path.join(log_dir, 'eval'),
        eval_freq=50_000,
        n_eval_episodes=100,
        deterministic=True,
        verbose=1
    )
    lr_cb = LinearLRDecay(TOTAL, initial_lr=3e-4, final_lr=5e-5)

    model = PPO(
        policy=GNNActorCriticPolicy,
        env=train_env,
        verbose=1,
        n_steps=2048,
        batch_size=256,         # Tăng: gradient ổn định hơn khi 10 nodes
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.03,          # Cân bằng: không quá greedy, không quá random
        vf_coef=0.5,
        max_grad_norm=0.5,
        learning_rate=3e-4,
        tensorboard_log=log_dir,
        policy_kwargs=dict(
            num_nodes=NUM_NODES,
            gat_hidden=64,
            gat_heads=4,
            features_dim=256,
        )
    )

    n_params = sum(p.numel() for p in model.policy.parameters() if p.requires_grad)
    logger.info(f"GNN Policy params: {n_params:,}")
    logger.info(f"Training {TOTAL:,} timesteps... (ước tính ~2-3 giờ trên CPU)")

    model.learn(
        total_timesteps=TOTAL,
        callback=[checkpoint_cb, eval_cb, lr_cb],
        reset_num_timesteps=True
    )

    model.save(model_out)
    logger.info(f"✅ Model Phase 6 lưu tại: {model_out}")
    print(f"\n🎉 Training DGRL v6 hoàn tất! Model: {model_out}")


if __name__ == '__main__':
    main()
