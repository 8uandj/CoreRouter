from __future__ import annotations

import random
from pathlib import Path
from typing import Callable, Dict, List

import numpy as np

from .env_factory import make_env
from .metrics import RunMetrics
from .model_loader import build_model_from_policy_weights, load_normalizer, normalized_obs


EnvMaker = Callable[[], object]


def run_exhaustive(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int) -> RunMetrics:
    env = make_env_fn()
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics("exhaustive_pair_search", scenario, env.topo.topology_name, seed)
    env.reset(seed=seed)

    for _ in range(steps):
        snap_state = env._state.copy()
        snap_req = dict(env._current_req)
        snap_step = env.current_step
        snap_active = list(env.active_flows)
        snap_bw = env._link_bw.copy()

        best_reward = -np.inf
        best_action = [0, 0]
        for v_place in range(env.num_nodes):
            for v_route in range(env.num_nodes):
                _restore_env(env, snap_state, snap_req, snap_step, snap_active, snap_bw)
                _, reward, _, _, _ = env.step([v_place, v_route])
                if reward > best_reward:
                    best_reward = reward
                    best_action = [v_place, v_route]

        _restore_env(env, snap_state, snap_req, snap_step, snap_active, snap_bw)
        _, reward, done, _, info = env.step(best_action)
        metrics.collect(info, reward)
        if done:
            env.reset(seed=seed)
    env.close()
    return metrics


def run_greedy(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int) -> RunMetrics:
    env = make_env_fn()
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics("traditional_greedy", scenario, env.topo.topology_name, seed)
    state, _ = env.reset(seed=seed)
    for _ in range(steps):
        free_cpu = [env.max_cpu - env._state[i * 3] for i in range(env.num_nodes)]
        v_place = int(np.argmax(free_cpu))
        v_route = int(np.argmin([
            np.inf if node == v_place else env.latency_matrix[v_place][node]
            for node in range(env.num_nodes)
        ]))
        state, reward, done, _, info = env.step([v_place, v_route])
        metrics.collect(info, reward)
        if done:
            state, _ = env.reset(seed=seed)
    env.close()
    return metrics


def run_saf_h(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int) -> RunMetrics:
    env = make_env_fn()
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics("saf_h", scenario, env.topo.topology_name, seed)
    state, _ = env.reset(seed=seed)
    for _ in range(steps):
        valid_actions = []
        cpu_req = env._current_req.get('cpu', 0.0)
        ram_req = env._current_req.get('ram', 0.0)
        msd_req = env._current_req.get('msd', 1)
        bw_req = cpu_req * 10.0
        
        for place in range(env.num_nodes):
            cpu_curr = env._state[place * 3]
            ram_curr = env._state[place * 3 + 1]
            if cpu_curr + cpu_req > env.max_cpu or ram_curr + ram_req > env.max_ram:
                continue
            for route in range(env.num_nodes):
                if place != route and env._link_bw[place][route] < bw_req:
                    continue
                hop_count = env.topo.get_hop_distance(place, route)
                msd_curr = env._state[route * 3 + 2]
                if msd_curr + msd_req + hop_count <= env.node_msd_limits[route]:
                    valid_actions.append([place, route])
        
        if not valid_actions:
            v_place, v_route = 0, 0
        else:
            best_action = None
            best_cost = np.inf
            for place, route in valid_actions:
                cpu_util = (env._state[place * 3] + cpu_req) / env.max_cpu
                latency = env.latency_matrix[place][route]
                hop_count = env.topo.get_hop_distance(place, route)
                cost = latency * 0.5 + cpu_util * 100.0 + hop_count * 5.0
                if cost < best_cost:
                    best_cost = cost
                    best_action = [place, route]
            v_place, v_route = best_action
            
        state, reward, done, _, info = env.step([v_place, v_route])
        metrics.collect(info, reward)
        if done:
            state, _ = env.reset(seed=seed)
    env.close()
    return metrics

def run_decoupled(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int) -> RunMetrics:
    env = make_env_fn()
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics("decoupled_ai", scenario, env.topo.topology_name, seed)
    state, _ = env.reset(seed=seed)
    for _ in range(steps):
        cpu_loads = [state[i * env.NODE_FEAT_DIM] for i in range(env.num_nodes)]
        v_place = int(np.argmin(cpu_loads))
        neighbors = np.where(env.topo.adj_matrix[v_place] > 0)[0]
        if len(neighbors) > 0:
            ram_loads = [state[node * env.NODE_FEAT_DIM + 1] for node in neighbors]
            v_route = int(neighbors[np.argmin(ram_loads)])
        else:
            cpu_copy = cpu_loads.copy()
            cpu_copy[v_place] = np.inf
            v_route = int(np.argmin(cpu_copy))
        state, reward, done, _, info = env.step([v_place, v_route])
        metrics.collect(info, reward)
        if done:
            state, _ = env.reset(seed=seed)
    env.close()
    return metrics


def run_jo_vppm(
    make_env_fn: EnvMaker,
    model_path: Path,
    norm_path: Path,
    scenario: str,
    steps: int,
    seed: int,
) -> RunMetrics:
    raw_env = make_env_fn()
    raw_env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics("harp", scenario, raw_env.topo.topology_name, seed)

    if not model_path.exists() or not norm_path.exists():
        raw_env.close()
        raise FileNotFoundError(
            f"HARP model not found.\n"
            f"  model_path: {model_path}\n"
            f"  norm_path:  {norm_path}\n"
            f"Make sure Cell 4 training completed for topology={raw_env.topo.topology_name}."
        )

    try:
        model = build_model_from_policy_weights(raw_env, model_path)
    except RuntimeError as e:
        raw_env.close()
        raise RuntimeError(
            f"HARP model size mismatch for topology={raw_env.topo.topology_name} "
            f"(num_nodes={raw_env.topo.num_nodes}, action_space={raw_env.topo.num_nodes**2}).\n"
            f"The model at {model_path} was trained with a different env. Run Cell 4 to retrain.\n"
            f"Original error: {e}"
        ) from e
    normalizer = load_normalizer(norm_path, model.get_env())
    obs, _ = raw_env.reset(seed=seed)

    for _ in range(steps):
        masks = np.array([raw_env.action_masks()])
        obs_norm = normalized_obs(normalizer, obs)
        action, _ = model.predict(obs_norm, action_masks=masks, deterministic=True)
        obs, reward, done, _, info = raw_env.step(action[0])
        metrics.collect(info, reward)
        if done:
            obs, _ = raw_env.reset(seed=seed)
    raw_env.close()
    return metrics


def _restore_env(env, state, req, step, active, bw) -> None:
    env._state = state.copy()
    env._current_req = dict(req)
    env.current_step = step
    env.active_flows.clear()
    env.active_flows.extend([dict(flow) for flow in active])
    env._link_bw = bw.copy()


def run_all_algorithms(
    make_env_fn: EnvMaker,
    scenario: str,
    steps: int,
    seed: int,
    model_path: Path,
    norm_path: Path,
    include_exhaustive: bool,
) -> Dict[str, RunMetrics]:
    results: Dict[str, RunMetrics] = {}
    if include_exhaustive:
        results["exhaustive_pair_search"] = run_exhaustive(make_env_fn, scenario, steps, seed)
    results["traditional_greedy"] = run_greedy(make_env_fn, scenario, steps, seed)
    results["saf_h"] = run_saf_h(make_env_fn, scenario, steps, seed)
    results["decoupled_ai"] = run_decoupled(make_env_fn, scenario, steps, seed)
    results["harp"] = run_jo_vppm(make_env_fn, model_path, norm_path, scenario, steps, seed)
    return results
