import zipfile
import json
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
import cloudpickle

model_path = "results/models/dgrl_v10_final_vietnam.zip"
with zipfile.ZipFile(model_path, "r") as z:
    with z.open("data") as f:
        data = json.loads(f.read().decode())
        print("policy_class:", data['policy_class'])
    with z.open("custom_objects") as f:
        custom = cloudpickle.loads(f.read())
        print(custom)
