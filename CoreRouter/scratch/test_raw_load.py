import sys
import os
import zipfile
import torch
import numpy as np
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.rewards import RewardCalculator
from src.orchestration.jo_vdpr.topology import TopologyManager
from src.infrastructure.persistence.csv_repository import CSVRepository
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy

topo_name = "vietnam"
topo = TopologyManager(topo_name)
repo = CSVRepository("data/real_telecom_combined.csv")
env = JOVDPREnv(repository=repo, reward_calculator=RewardCalculator(lambda_latency=-50.0), topology_manager=topo, episode_length=100)

vec_env = DummyVecEnv([lambda: env])
vec_env = VecNormalize.load("results/models/vec_normalize_v10_vietnam.pkl", vec_env)
vec_env.training = False
vec_env.norm_reward = False

policy_kwargs = dict(
    features_extractor_class=GNNActorCriticPolicy.features_extractor_class,
    num_nodes=topo.num_nodes,
    adj_matrix=topo.adj_matrix,
    gat_hidden=64,
    gat_heads=4,
    features_dim=256,
    net_arch=dict(pi=[256, 128], vf=[256, 128])
)
print("Creating dummy PPO model...")
model = MaskablePPO(GNNActorCriticPolicy, vec_env, policy_kwargs=policy_kwargs, device="cpu")

print("Extracting weights from ZIP...")
model_path = "results/models/dgrl_v10_final_vietnam.zip"
import zipfile
import io
with zipfile.ZipFile(model_path, "r") as z:
    with z.open("policy.pth") as f:
        buffer = io.BytesIO(f.read())
        state_dict = torch.load(buffer, map_location="cpu", weights_only=False)

print("Loading weights into policy...")
model.policy.load_state_dict(state_dict)
print("SUCCESS!")
