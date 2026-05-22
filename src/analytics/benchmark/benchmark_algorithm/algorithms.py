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
    metrics = RunMetrics("jo_vppm", scenario, raw_env.topo.topology_name, seed)

    if not model_path.exists() or not norm_path.exists():
        raw_env.close()
        return metrics

    model = build_model_from_policy_weights(raw_env, model_path)
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
    results["decoupled_ai"] = run_decoupled(make_env_fn, scenario, steps, seed)
    results["jo_vppm"] = run_jo_vppm(make_env_fn, model_path, norm_path, scenario, steps, seed)
    return results
