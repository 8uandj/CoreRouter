import zipfile
import json
import torch
from pathlib import Path

model_path = "results/models/dgrl_v10_final_vietnam.zip"
print("Unzipping...")
with zipfile.ZipFile(model_path, "r") as z:
    with z.open("data") as f:
        data = json.loads(f.read().decode())
        print(data.keys())
    
    with z.open("policy.optimizer.pth") as f:
        print("policy.optimizer.pth found!")
    
    with z.open("policy.pth") as f:
        print("Loading policy.pth...")
        state_dict = torch.load(f, map_location="cpu")
        print("Successfully loaded policy.pth!")
