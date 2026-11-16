import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sb3_contrib import MaskablePPO
from src.orchestration.jo_vdpr.gnn_policy import GNNActorCriticPolicy

model_path = "results/models/dgrl_v10_final_vietnam.zip"
print("Attempting to load model...")
try:
    model = MaskablePPO.load(model_path, device="cpu")
    print("Model loaded successfully!")
except Exception as e:
    print(f"Exception: {e}")
