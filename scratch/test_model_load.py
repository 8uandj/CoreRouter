
import torch
import numpy as np
from sb3_contrib import MaskablePPO
from src.orchestration.jo_vdpr.env import JOVDPREnv
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy
from src.core.interfaces.repository import IRepository

class MockRepo(IRepository):
    def get_next_entry(self, step):
        return {"cpu": 10, "ram": 10, "msd": 2, "service_type": "Video", "ddos": 0}
    def get_all(self): return []
    def add(self, entity): pass

def test_load():
    model_path = "/home/hung8uandj/Study/CoreRouter/results/models/dgrl_v8.zip"
    env = JOVDPREnv(repository=MockRepo(), episode_length=1)
    
    try:
        model = MaskablePPO.load(model_path, env=env)
        print("Model loaded successfully!")
        obs, _ = env.reset()
        action_masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=action_masks, deterministic=True)
        print(f"Prediction success: {action}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_load()
