from __future__ import annotations

import random
import copy
import time
from pathlib import Path
from typing import Callable, Dict, List

import numpy as np

from .env_factory import make_env
from .metrics import RunMetrics
from .model_loader import build_model_from_policy_weights, load_normalizer, normalized_obs


EnvMaker = Callable[[], object]


def run_exhaustive(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int, protected: bool = True) -> RunMetrics:
    env = make_env_fn()
    env.enforce_resource_constraints = protected
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics(f"exhaustive_pair_search_{'protected' if protected else 'unprotected'}", scenario, env.topo.topology_name, seed)
    env.reset(seed=seed)
    metrics.start_clock()

    for _ in range(steps):
        decision_start = time.perf_counter()
        snapshot = _snapshot_env(env)

        best_reward = -np.inf
        best_action = [0, 0]
        for v_place in range(env.num_nodes):
            for v_route in range(env.num_nodes):
                _restore_env(env, snapshot)
                _, reward, _, _, _ = env.step([v_place, v_route])
                if reward > best_reward:
                    best_reward = reward
                    best_action = [v_place, v_route]

        _restore_env(env, snapshot)
        _, reward, done, _, info = _step_and_collect(
            env, best_action, metrics, decision_start,
            {"candidate_search_ms": (time.perf_counter() - decision_start) * 1000.0},
        )
        if done:
            env.reset(seed=seed)
    metrics.stop_clock()
    env.close()
    return metrics


def run_greedy(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int, protected: bool = True) -> RunMetrics:
    env = make_env_fn()
    env.enforce_resource_constraints = protected
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics(f"traditional_greedy_{'protected' if protected else 'unprotected'}", scenario, env.topo.topology_name, seed)
    state, _ = env.reset(seed=seed)
    metrics.start_clock()
    for _ in range(steps):
        decision_start = time.perf_counter()
        free_cpu = [env.max_cpu - env._state[i * 3] for i in range(env.num_nodes)]
        v_place = int(np.argmax(free_cpu))
        v_route = int(np.argmin([
            np.inf if node == v_place else env.latency_matrix[v_place][node]
            for node in range(env.num_nodes)
        ]))
        selection_ms = (time.perf_counter() - decision_start) * 1000.0
        state, reward, done, info = _step_and_collect(
            env, [v_place, v_route], metrics, decision_start,
            {"heuristic_selection_ms": selection_ms},
        )
        if done:
            state, _ = env.reset(seed=seed)
    metrics.stop_clock()
    env.close()
    return metrics


def run_saf_h(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int, protected: bool = True) -> RunMetrics:
    env = make_env_fn()
    env.enforce_resource_constraints = protected
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics(f"saf_h_{'protected' if protected else 'unprotected'}", scenario, env.topo.topology_name, seed)
    state, _ = env.reset(seed=seed)
    metrics.start_clock()
    for _ in range(steps):
        decision_start = time.perf_counter()
        candidate_start = time.perf_counter()
        valid_actions = []
        cpu_req = env._current_req.get('cpu', 0.0)
        ram_req = env._current_req.get('ram', 0.0)
        msd_req = env._current_req.get('msd', 1)
        bw_req = cpu_req * 10.0
        
        for place in range(env.num_nodes):
            cpu_curr = env._state[place * 3]
            ram_curr = env._state[place * 3 + 1]
            if protected and (cpu_curr + cpu_req > env.max_cpu or ram_curr + ram_req > env.max_ram):
                continue
            for route in range(env.num_nodes):
                if protected and place != route and env._link_bw[place][route] < bw_req:
                    continue
                if not protected or msd_req <= env.node_msd_limits[route]:
                    valid_actions.append([place, route])
        
        feasible_set_ms = (time.perf_counter() - candidate_start) * 1000.0
        selection_start = time.perf_counter()
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
            
        heuristic_selection_ms = (time.perf_counter() - selection_start) * 1000.0
        state, reward, done, info = _step_and_collect(
            env, [v_place, v_route], metrics, decision_start,
            {"feasible_set_ms": feasible_set_ms, "heuristic_selection_ms": heuristic_selection_ms},
        )
        if done:
            state, _ = env.reset(seed=seed)
    metrics.stop_clock()
    env.close()
    return metrics

def run_decoupled(make_env_fn: EnvMaker, scenario: str, steps: int, seed: int, protected: bool = True) -> RunMetrics:
    env = make_env_fn()
    env.enforce_resource_constraints = protected
    env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics(f"decoupled_ai_{'protected' if protected else 'unprotected'}", scenario, env.topo.topology_name, seed)
    state, _ = env.reset(seed=seed)
    metrics.start_clock()
    for _ in range(steps):
        decision_start = time.perf_counter()
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
        selection_ms = (time.perf_counter() - decision_start) * 1000.0
        state, reward, done, info = _step_and_collect(
            env, [v_place, v_route], metrics, decision_start,
            {"heuristic_selection_ms": selection_ms},
        )
        if done:
            state, _ = env.reset(seed=seed)
    metrics.stop_clock()
    env.close()
    return metrics


def run_jo_vppm(
    make_env_fn: EnvMaker,
    model_path: Path,
    norm_path: Path,
    scenario: str,
    steps: int,
    seed: int,
    protected: bool = True,
) -> RunMetrics:
    raw_env = make_env_fn()
    raw_env.enforce_resource_constraints = protected
    raw_env.traffic_scenario = scenario
    np.random.seed(seed)
    random.seed(seed)
    metrics = RunMetrics(f"harp_{'protected' if protected else 'unprotected'}", scenario, raw_env.topo.topology_name, seed)

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
    metrics.start_clock()

    for _ in range(steps):
        decision_start = time.perf_counter()
        mask_start = time.perf_counter()
        mask = raw_env.action_masks() if protected else np.ones(raw_env.action_space.n, dtype=bool)
        mask_ms = (time.perf_counter() - mask_start) * 1000.0
        mask_count = int(mask.sum())
        # MaskablePPO cannot form a valid distribution from an all-false mask.
        # Still query the policy on the same state, then let the shared runtime
        # admission boundary reject the selected pair and record mask exhaustion.
        prediction_mask = mask if mask_count else np.ones(raw_env.action_space.n, dtype=bool)
        masks = np.array([prediction_mask])
        normalization_start = time.perf_counter()
        obs_norm = normalized_obs(normalizer, obs)
        normalization_ms = (time.perf_counter() - normalization_start) * 1000.0
        inference_start = time.perf_counter()
        action, _ = model.predict(obs_norm, action_masks=masks, deterministic=True)
        inference_ms = (time.perf_counter() - inference_start) * 1000.0
        obs, reward, done, _, info = raw_env.step(action[0])
        info.update({
            "mask_candidate_count": mask_count,
            "mask_total_candidates": int(raw_env.action_space.n),
            "mask_empty": mask_count == 0,
            "decision_latency_ms": (time.perf_counter() - decision_start) * 1000.0 + float(info.get("state_construction_ms", 0.0)),
            "decision_components_ms": {
                "mask_construction_ms": mask_ms,
                "policy_inference_ms": inference_ms,
                "normalization_ms": normalization_ms,
            },
        })
        metrics.collect(info, reward)
        if done:
            obs, _ = raw_env.reset(seed=seed)
    metrics.stop_clock()
    raw_env.close()
    return metrics


def _snapshot_env(env) -> dict:
    return {
        "state": env._state.copy(),
        "request": copy.deepcopy(env._current_req),
        "step": env.current_step,
        "active": copy.deepcopy(list(env.active_flows)),
        "bandwidth": env._link_bw.copy(),
        "previous_place": env._prev_v1,
        "previous_route": env._prev_v2,
        "violation_window": copy.deepcopy(env._violation_window),
        "lifecycle_rng": copy.deepcopy(env.np_random.bit_generator.state),
        "traffic_rng": copy.deepcopy(env._traffic_rng.bit_generator.state),
        "chaos_stress": env._chaos_stress_state,
    }


def _step_and_collect(env, action, metrics, decision_start, components):
    state, reward, done, _, info = env.step(action)
    info["decision_latency_ms"] = (
        time.perf_counter() - decision_start
    ) * 1000.0 + float(info.get("state_construction_ms", 0.0))
    info["decision_components_ms"] = dict(components)
    metrics.collect(info, reward)
    return state, reward, done, info


def _restore_env(env, snapshot: dict) -> None:
    env._state = snapshot["state"].copy()
    env._current_req = copy.deepcopy(snapshot["request"])
    env.current_step = snapshot["step"]
    env.active_flows.clear()
    env.active_flows.extend(copy.deepcopy(snapshot["active"]))
    env._link_bw = snapshot["bandwidth"].copy()
    env._prev_v1 = snapshot["previous_place"]
    env._prev_v2 = snapshot["previous_route"]
    env._violation_window = copy.deepcopy(snapshot["violation_window"])
    env.np_random.bit_generator.state = copy.deepcopy(snapshot["lifecycle_rng"])
    env._traffic_rng.bit_generator.state = copy.deepcopy(snapshot["traffic_rng"])
    env._chaos_stress_state = snapshot["chaos_stress"]


def run_all_algorithms(
    make_env_fn: EnvMaker,
    scenario: str,
    steps: int,
    seed: int,
    model_path: Path,
    norm_path: Path,
    include_exhaustive: bool,
    include_unprotected: bool = True,
) -> Dict[str, RunMetrics]:
    results: Dict[str, RunMetrics] = {}
    protection_modes = [True, False] if include_unprotected else [True]
    for protected in protection_modes:
        suffix = "protected" if protected else "unprotected"
        if include_exhaustive:
            results[f"exhaustive_pair_search_{suffix}"] = run_exhaustive(make_env_fn, scenario, steps, seed, protected)
        results[f"traditional_greedy_{suffix}"] = run_greedy(make_env_fn, scenario, steps, seed, protected)
        results[f"saf_h_{suffix}"] = run_saf_h(make_env_fn, scenario, steps, seed, protected)
        results[f"decoupled_ai_{suffix}"] = run_decoupled(make_env_fn, scenario, steps, seed, protected)
        results[f"harp_{suffix}"] = run_jo_vppm(make_env_fn, model_path, norm_path, scenario, steps, seed, protected)
    return results
