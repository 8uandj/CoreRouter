#!/usr/bin/env python3
"""
benchmark_phase6.py — Automated Benchmark for 3S-COM Phase 6
=============================================================
PHASE 6 REFACTORED: Fixes State Desync, Joint-Constraint Paradox, and Data Drift.
"""

import argparse
import csv
import json
import logging
import random
import time
import os
import numpy as np
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# PHASE 6: Import Agent de chay Local (Fix Tử Huyệt 2 - State Desynchronization)
try:
    from src.ai.dgrl_agent import DGRLAgent
    from src.ai.heuristic import get_decoupled_action, ActionChoice, HardConstraintError
    from src.core.state_manager import NetworkStateManager
    AGENT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"AI Agent dependencies missing: {e}")
    AGENT_AVAILABLE = False

# ─── Cấu hình ──────────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000"
RESULTS_DIR = Path("results/benchmark_phase6")
NODE_MSD_LIMITS = [10, 10, 5, 5, 4, 8, 4, 5, 10, 5]
NODE_CPU_CAP    = [200, 150, 80, 80, 60, 150, 60, 80, 200, 80]
LATENCY_MATRIX = [
    [0,   1.2, 3.5, 7.0, 12.0, 14.5, 18.0, 19.5, 22.0, 24.5],
    [1.2, 0,   2.5, 6.0, 11.0, 13.5, 17.0, 18.5, 21.0, 23.5],
    [3.5, 2.5, 0,   3.5, 8.5,  11.0, 14.5, 16.0, 18.5, 21.0],
    [7.0, 6.0, 3.5, 0,   5.0,  7.5,  11.0, 12.5, 15.0, 17.5],
    [12.0,11.0,8.5, 5.0, 0,    2.5,  6.0,  7.5,  10.0, 12.5],
    [14.5,13.5,11.0,7.5, 2.5,  0,    3.5,  5.0,  7.5,  10.0],
    [18.0,17.0,14.5,11.0,6.0,  3.5,  0,    1.5,  4.0,  6.5 ],
    [19.5,18.5,16.0,12.5,7.5,  5.0,  1.5,  0,    2.5,  5.0 ],
    [22.0,21.0,18.5,15.0,10.0, 7.5,  4.0,  2.5,  0,    2.5 ],
    [24.5,23.5,21.0,17.5,12.5, 10.0, 6.5,  5.0,  2.5,  0   ],
]
SLA_CLASSES = ["urllc", "voip", "video", "data", "attack"]

AI_NODE_TO_K8S_HOSTNAME: Dict[int, str] = {
    0: "k8s-master", 1: "k8s-master", 2: "k8s-master",
    3: "worker1", 4: "worker1", 5: "worker1",
    6: "worker2", 7: "worker2", 8: "worker2", 9: "worker2",
}

@dataclass
class SFCRequest:
    source: int
    target: int
    cpu_req: float
    ram_req: float
    msd_req: int
    service_type: str
    alert_flag: bool = False

@dataclass
class BenchmarkResult:
    step: int
    method: str
    accepted: bool
    latency_ms: float
    msd_violation: bool
    placement_node: int
    k8s_hostname: str
    steering_latency_ms: float
    service_type: str
    reject_reason: str = ""

class LocalState:
    """Mô phỏng trạng thái mạng đồng bộ cho cả Heuristic và AI."""
    def __init__(self):
        from src.orchestration.jo_vdpr.topology import TopologyManager
        self.topology = TopologyManager()
        self.cpu_used = [0.0] * 10
        self.msd_used = [0.0] * 10

    def reset(self):
        self.cpu_used = [0.0] * 10
        self.msd_used = [0.0] * 10

    def try_reserve(self, v_place: int, v_route: int, cpu: float, msd_base: int) -> Tuple[bool, str]:
        # ALIGNMENT: env.py logic (Khong tinh hops vao rejection)
        msd_total = msd_base

        touched = {int(v_place), int(v_route)}
        for node in touched:
            if self.cpu_used[node] + cpu > NODE_CPU_CAP[node]:
                return False, "cpu_capacity"
            if self.msd_used[node] + msd_total > NODE_MSD_LIMITS[node]:
                return False, "msd_capacity"
        
        for node in touched:
            self.cpu_used[node] += cpu
            self.msd_used[node] += msd_total
        return True, ""

    def free(self, v_place: int, v_route: int, cpu: float, msd_base: int):
        # ALIGNMENT: env.py logic
        msd_total = msd_base
        touched = {int(v_place), int(v_route)}
        for node in touched:
            self.cpu_used[node] = max(0.0, self.cpu_used[node] - cpu)
            self.msd_used[node] = max(0.0, self.msd_used[node] - msd_total)

def generate_request(step: int, total_steps: int) -> SFCRequest:
    src = random.randint(0, 9)
    dst = random.randint(0, 9)
    while dst == src: dst = random.randint(0, 9)
    
    # Stress surge: Tang tai sau 50% steps
    is_stress = (step > total_steps // 2)
    cpu_base = 40 if is_stress else 10
    msd_base = 4 if is_stress else 1
    
    cpu = random.randint(cpu_base, cpu_base + 20)
    msd = random.randint(msd_base, msd_base + 2)
    svc = random.choice(SLA_CLASSES)
    return SFCRequest(src, dst, cpu, cpu*0.5, msd, svc, step % 30 == 0)

def run_benchmark(method: str, steps: int, dry_run: bool, seed: int) -> List[BenchmarkResult]:
    random.seed(seed)
    state = LocalState()
    results = []
    active_requests = []  # (v_place, v_route, cpu, msd, ttl)
    
    local_agent = None
    shared_manager = None
    if method in ["ai", "hybrid"] and AGENT_AVAILABLE:
        logging.info("Initializing Local DGRL Agent (Fix State Desync)...")
        local_agent = DGRLAgent()
        shared_manager = NetworkStateManager()
    
    for step in range(steps):
        # TTL Decay
        next_active = []
        for vp, vr, c, m, ttl in active_requests:
            if ttl > 1: next_active.append((vp, vr, c, m, ttl - 1))
            else: state.free(vp, vr, c, m)
        active_requests = next_active

        # SYNC: Dam bao AI Manager luon thay trang thai thuc cua Testbed
        if shared_manager:
            shared_manager._state[:, 0] = state.cpu_used
            shared_manager._state[:, 2] = state.msd_used

        req = generate_request(step, steps)
        node_id, route_id = -1, -1
        accepted = False
        msd_violation = False
        reject_reason = ""

        # Hybrid Decision Logic
        method_to_use = method
        if method == "hybrid" and shared_manager:
            snap = shared_manager.snapshot()
            if snap.global_utilization < 0.40:
                # Normal Load: Use Decoupled Heuristic
                from src.ai.heuristic import get_decoupled_action
                try:
                    decision = get_decoupled_action(snap, req)
                    node_id, route_id = decision.v_place, decision.v_route
                    method_to_use = "decoupled_via_hybrid" # Flag to skip AI block
                except:
                    method_to_use = "ai"
            else:
                method_to_use = "ai"
        
        if method_to_use == "ai" and local_agent and shared_manager:
            try:
                action_mask = shared_manager.action_mask(req)
                if not bool(action_mask.any()):
                    # Smart Admission Control: all actions are masked out.
                    # Calling MaskablePPO in this state may return a default invalid action.
                    raise HardConstraintError("no_safe_action_mask_all_false")
                decision = local_agent.get_action(shared_manager, req)
                node_id, route_id = decision.choice.v_place, decision.choice.v_route
            except HardConstraintError:
                # Smart Admission Control: no physically safe action remains.
                node_id, route_id = -1, -1
                reject_reason = "no_safe_action"
        elif method_to_use == "greedy":
            # Simple best-fit CPU
            best_node, max_cpu = -1, -1.0
            for i in range(10):
                free = NODE_CPU_CAP[i] - state.cpu_used[i]
                if free > max_cpu and free >= req.cpu_req:
                    max_cpu = free
                    best_node = i
            node_id, route_id = best_node, best_node
        elif method_to_use == "decoupled":
            node_id = random.randint(0, 9)
            route_id = node_id

        if node_id != -1:
            reserved, reserve_reason = state.try_reserve(node_id, route_id, req.cpu_req, req.msd_req)
            if reserved:
                accepted = True
            else:
                reject_reason = reserve_reason
                msd_violation = reserve_reason == "msd_capacity"
        elif not reject_reason:
            reject_reason = "no_candidate"

        if accepted:
            # Tăng TTL để gây nghẽn mạng thực thụ
            ttl = random.randint(50, 150) if step > steps // 2 else random.randint(20, 50)
            active_requests.append((node_id, route_id, req.cpu_req, req.msd_req, ttl))

        results.append(BenchmarkResult(
            step=step, method=method, accepted=accepted,
            latency_ms=LATENCY_MATRIX[req.source][node_id] + LATENCY_MATRIX[node_id][req.target] if accepted else 0,
            msd_violation=msd_violation,
            placement_node=node_id,
            k8s_hostname=AI_NODE_TO_K8S_HOSTNAME.get(node_id, "none"),
            steering_latency_ms=5.0 if accepted and method == "ai" else 0.0,
            service_type=req.service_type,
            reject_reason="" if accepted else reject_reason,
        ))
        
        if step % 50 == 0:
            acc_rate = sum(1 for r in results if r.accepted) / (step + 1) * 100
            logging.info(f"[{method:9}] Step {step:3}/{steps} | Accept={acc_rate:.1f}%")

    return results

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    summary = {}
    for method in ["ai", "decoupled", "greedy", "hybrid"]:
        print(f"\n--- Running {method.upper()} ---")
        results = run_benchmark(method, args.steps, True, args.seed)
        
        acc = sum(1 for r in results if r.accepted) / args.steps * 100
        msd_v = sum(1 for r in results if r.msd_violation) / args.steps * 100
        cpu_reject = sum(1 for r in results if r.reject_reason == "cpu_capacity") / args.steps * 100
        no_safe = sum(1 for r in results if r.reject_reason in {"no_safe_action", "no_candidate"}) / args.steps * 100
        lat = np.mean([r.latency_ms for r in results if r.accepted])
        
        summary[method] = {
            "Accept": acc,
            "MSD_Viol": msd_v,
            "CPU_Reject": cpu_reject,
            "NoSafe": no_safe,
            "Lat": lat,
        }
        print(
            f"RESULTS [{method}]: Accept={acc:.2f}%, MSD_Viol={msd_v:.2f}%, "
            f"CPU_Reject={cpu_reject:.2f}%, NoSafe={no_safe:.2f}%, Lat={lat:.2f}ms"
        )

    # Export to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULTS_DIR / f"phase6_final_{timestamp}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary["ai"].keys(), restval="method")
        f.write("method," + ",".join(summary["ai"].keys()) + "\n")
        for m, vals in summary.items():
            f.write(f"{m}," + ",".join(str(v) for v in vals.values()) + "\n")
    
    print(f"\n✅ Final results saved to {csv_path}")

if __name__ == "__main__":
    main()
