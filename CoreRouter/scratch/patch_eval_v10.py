import re

with open("src/analytics/benchmark_eval.py", "r") as f:
    eval_text = f.read()

# Replace V9 imports and models with V10
eval_text = eval_text.replace("from stable_baselines3 import PPO", "from sb3_contrib import MaskablePPO")
eval_text = eval_text.replace("from stable_baselines3.common.vec_env import DummyVecEnv", "from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize")

# Fix run_jo_vppm to use the zip unpickling method instead of MaskablePPO.load
old_run_jo_vppm = """def run_jo_vppm(env: JOVDPREnv, model_path: str, scenario: str = 'uniform') -> BenchmarkMetrics:"""
new_run_jo_vppm = """def run_jo_vppm(env: JOVDPREnv, model_path: str, norm_path: str, scenario: str = 'uniform') -> BenchmarkMetrics:"""
eval_text = eval_text.replace(old_run_jo_vppm, new_run_jo_vppm)

# Replace the inner body of run_jo_vppm
old_body = """    # Vá lỗi Generalization: Đè Node Features DIM của Model cũ
    import torch
    import torch.nn as nn
    
    # Init blank dummy model
    model = MaskablePPO(GNNActorCriticPolicy, env, policy_kwargs=dict(
        features_extractor_class=GNNActorCriticPolicy.features_extractor_class,
        num_nodes=env.num_nodes,
        adj_matrix=env.latency_matrix,
        gat_hidden=64, gat_heads=4, features_dim=256
    ), device="cpu")

    try:
        loaded = MaskablePPO.load(model_path, device="cpu")
        model.policy.load_state_dict(loaded.policy.state_dict(), strict=False)
    except:
        pass"""

new_body = """    import zipfile
    import io
    import torch
    import numpy as np
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    
    vec_env = DummyVecEnv([lambda: env])
    vec_env = VecNormalize.load(norm_path, vec_env)
    vec_env.training = False
    vec_env.norm_reward = False

    policy_kwargs = dict(
        num_nodes=env.num_nodes,
        adj_matrix=env.topo.adj_matrix,
        gat_hidden=64, gat_heads=4, features_dim=256,
        net_arch=dict(pi=[256, 128], vf=[256, 128])
    )
    model = MaskablePPO(GNNActorCriticPolicy, vec_env, policy_kwargs=policy_kwargs, device="cpu")

    try:
        with zipfile.ZipFile(model_path, "r") as z:
            with z.open("policy.pth") as f:
                buffer = io.BytesIO(f.read())
                state_dict = torch.load(buffer, map_location="cpu", weights_only=False)
        model.policy.load_state_dict(state_dict)
    except Exception as e:
        print(f"Bỏ qua model lỗi: {e}")"""

eval_text = eval_text.replace(old_body, new_body)

# Replace build_topology_env
old_build_env = """def build_topology_env(topology_name: str, data_path: str) -> JOVDPREnv:
    if topology_name == 'vietnam':
        from src.orchestration.jo_vdpr.topology import NUM_NODES, LATENCY_MATRIX, MAX_MSD_LIMITS, NODE_NAMES
    elif topology_name == 'nsfnet':
        from src.orchestration.jo_vdpr.topology_nsfnet import NUM_NODES, LATENCY_MATRIX, MAX_MSD_LIMITS, NODE_NAMES
    elif topology_name == 'geant2':
        from src.orchestration.jo_vdpr.topology_geant2 import NUM_NODES, LATENCY_MATRIX, MAX_MSD_LIMITS, NODE_NAMES
    else:
        raise ValueError("Invalid topology!")

    env = JOVDPREnv(
        repository=CSVRepository(data_path),
        reward_calculator=RewardCalculator(lambda_latency=-50.0),
        episode_length=100
    )
    env.num_nodes = NUM_NODES
    env.latency_matrix = LATENCY_MATRIX
    env.node_msd_limits = MAX_MSD_LIMITS
    env.node_names = NODE_NAMES
    
    return env"""

new_build_env = """def build_topology_env(topology_name: str, data_path: str) -> JOVDPREnv:
    from src.orchestration.jo_vdpr.topology import TopologyManager
    topo = TopologyManager(topology_name)
    env = JOVDPREnv(
        repository=CSVRepository(data_path),
        reward_calculator=RewardCalculator(lambda_latency=-50.0),
        topology_manager=topo,
        episode_length=100
    )
    return env"""

eval_text = eval_text.replace(old_build_env, new_build_env)

# Correct usages of model_v9
eval_text = eval_text.replace("m_ppo = run_jo_vppm(make_env(), model_path, scenario)", 
                              "norm_p = os.path.join(root_dir, 'results', 'models', f'vec_normalize_v10_{topology}.pkl')\n    m_ppo = run_jo_vppm(make_env(), model_path, norm_p, scenario)")

eval_text = eval_text.replace("model_v9   = os.path.join(root_dir, 'results', 'models', 'dgrl_v9.zip')", 
                              "")
eval_text = eval_text.replace("model_v8   = os.path.join(root_dir, 'results', 'models', 'dgrl_v8.zip')",
                              "")
eval_text = eval_text.replace("model_path = model_v9 if os.path.exists(model_v9) else model_v8",
                              "")
eval_text = eval_text.replace("r = run_one_scenario(topo, sc, data_path, model_path, root_dir)",
                              "model_path = os.path.join(root_dir, 'results', 'models', f'dgrl_v10_final_{topo}.zip')\n                r = run_one_scenario(topo, sc, data_path, model_path, root_dir)")

# Fix step vs steps inside inference loops:
# v10 env uses action_masks, so we need to inject that logic into the evaluate step
vec_env_eval_loop = """        obs = vec_env.reset()
        for idx in range(NUM_EPISODES):
            apply_traffic_scenario(env, scenario, idx)
            masks = np.array([env.action_masks()])
            a, _ = model.predict(obs, action_masks=masks, deterministic=True)
            obs, reward, done, infos = vec_env.step(a)
            info = infos[0]"""

eval_text = re.sub(r'        for idx in range\(NUM_EPISODES\):.*?a, _ = model\.predict\(obs, deterministic=True\).*?obs, reward, done, .*?, info = env\.step\(a\)', vec_env_eval_loop, eval_text, flags=re.DOTALL)


with open("src/analytics/benchmark_v10_detailed.py", "w") as f:
    f.write(eval_text)

print("Generated benchmark_v10_detailed.py")
