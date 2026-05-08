import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.optimization.trainer import PPOTrainer

def main():
    print("="*60)
    print("  JO-VDPR Training (MDP v3 - Traffic Classes & BSID Penalty)")
    print("="*60)

    repo_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'real_telecom_combined.csv')
    repo = CSVRepository(repo_path)
    
    print(f"Loaded dataset: {len(repo.dataset)} flows")

    reward_calc = RewardCalculator()
    env = JOVDPREnv(repository=repo, reward_calculator=reward_calc, num_nodes=5)

    base_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'results')
    
    trainer = PPOTrainer(
        env=env,
        log_dir=os.path.join(base_dir, 'logs', 'ppo'),
        model_path=os.path.join(base_dir, 'models', 'ppo_jo_vdpr_model.zip')
    )

    print("Khởi tạo PPO model với kiến trúc mạng [256, 256]...")
    trainer.build_model()
    
    print("Bắt đầu huấn luyện... (Mục tiêu: 500,000 steps)")
    trainer.train(total_timesteps=500_000)

if __name__ == "__main__":
    main()
