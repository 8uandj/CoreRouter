"""
train_v11.py — JO-VPPM Training Phase 11 (Path-Aware MSD & 10-Node Topology)

Chạy:
    python -m src.analytics.training.train_v11 --topology vietnam
    python -m src.analytics.training.train_v11 --topology nsfnet
"""

import os
import sys
import logging
import argparse
import numpy as np

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor, VecNormalize, DummyVecEnv
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback, CallbackList

from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env     import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.orchestration.jo_vdpr.topology import TopologyManager


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("DGRL-v11")

# ── Hyperparameters ──────────────────────────────────────────
N_ENVS       = 10   
N_STEPS      = 512
BATCH_SIZE   = 256
TOTAL_STEPS  = 3_000_000  # Tăng lên 3M cho 10-node topology
LEARNING_RATE = 3e-4 


class EntropyDecayCallback(BaseCallback):
    def __init__(self, initial: float = 0.05, final: float = 0.00005,
                 total_steps: int = TOTAL_STEPS):
        super().__init__()
        self.initial     = initial
        self.final       = final
        self.total_steps = total_steps

    def _on_step(self) -> bool:
        progress = self.num_timesteps / self.total_steps
        new_ent = self.final + 0.5 * (self.initial - self.final) * (
            1 + np.cos(np.pi * progress)
        )
        self.model.ent_coef = float(new_ent)
        return True


class AdaptivePenaltyCallback(BaseCallback):
    def __init__(self,
                 reward_calculator: RewardCalculator,
                 target_rate: float = 0.015,   
                 update_freq: int   = 5120,
                 lr_lambda:   float = 10.0,
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
            for inf in self.locals['infos']:
                if 'latency_violation_rate' in inf:
                    self._viol_buffer.append(inf['latency_violation_rate'])

        if self.n_calls % self.update_freq == 0 and self._viol_buffer:
            avg_viol = float(np.mean(self._viol_buffer))
            self._viol_buffer.clear()

            delta = self.lr_lambda * (avg_viol - self.target_rate)
            current_lambda = self.reward_calc.lambda_latency
            new_lambda = np.clip(current_lambda - delta, self.lambda_min, self.lambda_max)

            self.reward_calc.update_lambda_latency(new_lambda)
            if self.verbose > 0:
                logger.info(f"Step {self.num_timesteps}: SLA Viol = {avg_viol:.2%} "
                            f"| Target = {self.target_rate:.2%} | λ_SLA = {new_lambda:.1f}")

            if hasattr(self.training_env, 'env_method'):
                self.training_env.env_method('update_reward_lambda', new_lambda)

        return True


def make_env(rank: int, seed: int, data_path: str, topology_name: str, lambda_ref: float = -50.0):
    def _init():
        topo = TopologyManager(topology_name)
        reward_calc = RewardCalculator(lambda_latency=lambda_ref, evacuation_penalty=-50.0, msd_violation_penalty=-50.0)
        repo        = CSVRepository(data_path)
        env         = JOVDPREnv(repository=repo, reward_calculator=reward_calc,
                                topology_manager=topo, episode_length=100)
        env.reset(seed=seed + rank)
        return env
    set_random_seed(seed)
    return _init

def linear_schedule(initial_value: float):
    def func(progress_remaining: float) -> float:
        return progress_remaining * initial_value
    return func

def train_dgrl(topology_name: str):
    logger.info(f"BẮT ĐẦU HUẤN LUYỆN JO-VPPM V11 TRÊN MẠNG: {topology_name.upper()}")
    
    # ── Path Setup ───────────────────────────────────────────────
    BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    DATA_PATH    = os.path.join(BASE_DIR, 'data', 'telecom_trace.csv') # Dùng file trace gốc hoặc combined tùy ý
    RES_DIR      = os.path.join(BASE_DIR, 'results')
    MODEL_DIR    = os.path.join(RES_DIR, 'models', 'v11')
    TENSORBOARD  = os.path.join(RES_DIR, 'logs', f'dgrl_v11_tb_{topology_name}')
    
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(TENSORBOARD, exist_ok=True)

    # ── Topology Extract ─────────────────────────────────────────
    topo = TopologyManager(topology_name)
    num_nodes  = topo.num_nodes
    adj_matrix = topo.adj_matrix

    logger.info(f"Topology: {topology_name} ({num_nodes} nodes). Load DATA: {DATA_PATH}")

    # ── Vectorized Env ───────────────────────────────────────────
    train_env = SubprocVecEnv([
        make_env(i, seed=42, data_path=DATA_PATH, topology_name=topology_name, lambda_ref=-100.0)
        for i in range(N_ENVS)
    ])
    train_env = VecMonitor(train_env)
    train_env = VecNormalize(train_env, norm_obs=True, norm_reward=True, clip_obs=10.0, gamma=0.99)

    eval_env = DummyVecEnv([
        make_env(99, seed=999, data_path=DATA_PATH, topology_name=topology_name, lambda_ref=-50.0)
    ])
    eval_env = VecMonitor(eval_env)
    eval_env = VecNormalize(eval_env, norm_obs=True, norm_reward=False, training=False)

    # ── Cấu trúc GNN Policy ──────────────────────────────────────
    policy_kwargs = dict(
        num_nodes=num_nodes,
        adj_matrix=adj_matrix,
        gat_hidden=64,
        gat_heads=4,
        features_dim=256,
        net_arch=dict(pi=[256, 128], vf=[256, 128])
    )

    # ── Khởi tạo Mô Hình ─────────────────────────────────────────
    model = MaskablePPO(
        policy=GNNActorCriticPolicy,
        env=train_env,
        learning_rate=linear_schedule(LEARNING_RATE),
        n_steps=N_STEPS,
        batch_size=BATCH_SIZE,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.05,
        vf_coef=0.7,
        max_grad_norm=0.5,
        policy_kwargs=policy_kwargs,
        tensorboard_log=TENSORBOARD,
        verbose=1,
        seed=42
    )

    # ── Callbacks ────────────────────────────────────────────────
    base_reward_calc = RewardCalculator(lambda_latency=-100.0)
    cb_adaptive = AdaptivePenaltyCallback(base_reward_calc, target_rate=0.015, update_freq=N_STEPS*N_ENVS)
    cb_entropy  = EntropyDecayCallback(initial=0.05, final=0.00005, total_steps=TOTAL_STEPS)

    eval_callback = MaskableEvalCallback(
        eval_env,
        best_model_save_path=MODEL_DIR,
        log_path=TENSORBOARD,
        eval_freq=max(10_000 // N_ENVS, 1),
        deterministic=True,
        render=False
    )
    checkpoint_callback = CheckpointCallback(
        save_freq=max(500_000 // N_ENVS, 1),
        save_path=MODEL_DIR,
        name_prefix=f'dgrl_v11_ckpt_{topology_name}'
    )

    callbacks = CallbackList([cb_adaptive, cb_entropy, eval_callback, checkpoint_callback])

    # ── Training ─────────────────────────────────────────────────
    logger.info("Khởi động quá trình Huấn Luyện (Level 0)...")
    try:
        model.learn(total_timesteps=TOTAL_STEPS, callback=callbacks,
                    tb_log_name=f"run_v11_{topology_name}")
        
        final_model_path = os.path.join(MODEL_DIR, f'dgrl_v11_{topology_name}.zip')
        model.save(final_model_path)
        logger.info(f"Huấn luyện thành công! Đã lưu: {final_model_path}")
        
        env_path = os.path.join(MODEL_DIR, f'vec_normalize_v11_{topology_name}.pkl')
        train_env.save(env_path)
        logger.info(f"Đã lưu VecNormalize stats: {env_path}")
        
    except KeyboardInterrupt:
        logger.warning("Bị hủy bởi user! Lưu checkpoint khẩn...")
        model.save(os.path.join(MODEL_DIR, f'dgrl_v11_interrupted_{topology_name}.zip'))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JO-VPPM v11 Trainer")
    parser.add_argument("--topology", type=str, default="vietnam", choices=["vietnam", "nsfnet", "geant2"])
    args = parser.parse_args()
    
    train_dgrl(args.topology)
