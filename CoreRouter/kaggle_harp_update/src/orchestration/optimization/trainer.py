import os
import logging
from typing import Optional
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback, BaseCallback
from src.orchestration.jo_vdpr.env import JOVDPREnv

logger = logging.getLogger("PPOTrainer")

class LearningRateSchedule(BaseCallback):
    def __init__(self, total_timesteps: int, initial_lr=3e-4, final_lr=5e-5):
        super().__init__()
        self.total_timesteps = total_timesteps
        self.initial_lr = initial_lr
        self.final_lr = final_lr

    def _on_step(self):
        progress = self.num_timesteps / self.total_timesteps
        lr = self.initial_lr - progress * (self.initial_lr - self.final_lr)
        self.model.policy.optimizer.param_groups[0]['lr'] = lr
        return True

class PPOTrainer:
    def __init__(self, 
                 env: JOVDPREnv, 
                 log_dir="results/logs/ppo", 
                 model_path="results/models/ppo_jo_vdpr_model"):
        self.env = env
        self.log_dir = log_dir
        self.model_path = model_path
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def build_model(self, lr=3e-4):
        policy_kwargs = dict(net_arch=[dict(pi=[256, 256], vf=[256, 256])])
        
        self.model = PPO(
            "MlpPolicy",
            self.env,
            verbose=1,
            learning_rate=lr,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            ent_coef=0.01,
            policy_kwargs=policy_kwargs,
            tensorboard_log=self.log_dir,
        )
        return self.model

    def train(self, total_timesteps=500_000):
        checkpoint_cb = CheckpointCallback(
            save_freq=50_000, 
            save_path=os.path.join(self.log_dir, "checkpoints"),
            name_prefix="jo_vdpr"
        )
        lr_cb = LearningRateSchedule(total_timesteps)

        self.model.learn(
            total_timesteps=total_timesteps,
            callback=[checkpoint_cb, lr_cb],
            reset_num_timesteps=True
        )
        self.model.save(self.model_path)
        logger.info(f"Model saved to {self.model_path}")
