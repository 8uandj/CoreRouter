from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Tuple

from .exporters import write_records_csv
from .metrics import summarize_records
from .models import RequestRecord, RequestSpec, ScenarioDefinition
from .runner import stable_name_offset


BASELINE_ALGORITHMS = ["jo_vppm", "heuristic", "greedy", "decoupled"]


class BaselineSimulator:
    """Local baseline runner using the same request stream as runtime scenarios."""

    def __init__(self, seed: int, steps: int = 0) -> None:
        self.seed = seed
        self.steps = steps

    def run(
        self,
        scenario: ScenarioDefinition,
        algorithm: str,
        output_dir: Path,
    ) -> Tuple[List[RequestRecord], object]:
        if algorithm not in BASELINE_ALGORITHMS:
            raise ValueError(f"Unsupported baseline algorithm: {algorithm}")

        import random
        from src.ai.heuristic import (
            HardConstraintError,
            get_decoupled_action,
            get_resilience_safe_action,
        )
        from src.ai.dgrl_agent import get_dgrl_agent
        from src.core.state_manager import NetworkStateManager

        rng = random.Random(self.seed + stable_name_offset(scenario.name))
        state_manager = NetworkStateManager()
        dgrl_agent = get_dgrl_agent() if algorithm == "jo_vppm" else None
        if dgrl_agent is not None:
            warmup_req = scenario.request_factory(0, self.steps or scenario.default_steps, rng)
            if warmup_req is not None:
                dgrl_agent.get_action(state_manager, warmup_req)
            else:
                dgrl_agent.get_action(
                    state_manager,
                    RequestSpec(service_type="Data", cpu_req=8, ram_req=4, msd_req=1),
                )
            rng = random.Random(self.seed + stable_name_offset(scenario.name))
        records: List[RequestRecord] = []
        active: List[Dict[str, object]] = []
        steps = self.steps or scenario.default_steps

        for step in range(steps):
            remaining: List[Dict[str, object]] = []
            for reservation in active:
                if int(reservation["expire_step"]) <= step:
                    state_manager.free_resources(
                        int(reservation["v_place"]),
                        int(reservation["v_route"]),
                        float(reservation["cpu_req"]),
                        float(reservation["ram_req"]),
                        int(reservation["msd_req"]),
                    )
                else:
                    remaining.append(reservation)
            active = remaining

            spec = scenario.request_factory(step, steps, rng)
            if spec is None:
                continue

            start = time.perf_counter()
            accepted = False
            reject_reason = ""
            v_place = None
            v_route = None
            method_used = algorithm

            if spec.alert_flag:
                state_manager.set_forecast_alert(True)

            try:
                snapshot = state_manager.snapshot()
                if algorithm == "jo_vppm":
                    decision = dgrl_agent.get_action(state_manager, spec)
                    v_place = int(decision.choice.v_place)
                    v_route = int(decision.choice.v_route)
                    method_used = "JO-VPPM" if decision.model_loaded else "JO-VPPM fallback"
                elif algorithm == "heuristic":
                    decision = get_resilience_safe_action(snapshot, spec)
                    v_place = int(decision.v_place)
                    v_route = int(decision.v_route)
                    method_used = "Resilience Heuristic"
                elif algorithm == "decoupled":
                    decision = get_decoupled_action(snapshot, spec)
                    v_place = int(decision.v_place)
                    v_route = int(decision.v_route)
                    method_used = "Decoupled Heuristic"
                elif algorithm == "greedy":
                    v_place, v_route = self._greedy_choice(snapshot, spec)
                    method_used = "Greedy"

                accepted, error = state_manager.try_reserve(
                    v_place,
                    v_route,
                    spec.cpu_req,
                    spec.ram_req,
                    spec.msd_req,
                    vnf_name=f"{algorithm}-{scenario.name}-{step}",
                )
                if not accepted:
                    reject_reason = error or "reserve_failed"
            except HardConstraintError as exc:
                reject_reason = str(exc)
            except Exception as exc:
                reject_reason = f"error:{exc}"

            latency_ms = round((time.perf_counter() - start) * 1000.0, 3)
            if accepted and v_place is not None and v_route is not None:
                active.append(
                    {
                        "expire_step": step + spec.ttl_steps,
                        "v_place": v_place,
                        "v_route": v_route,
                        "cpu_req": spec.cpu_req,
                        "ram_req": spec.ram_req,
                        "msd_req": spec.msd_req,
                    }
                )

            records.append(
                RequestRecord(
                    algorithm=algorithm,
                    scenario=scenario.name,
                    step=step,
                    accepted=accepted,
                    status_code=200 if accepted else 409,
                    decision_latency_ms=latency_ms,
                    service_type=spec.service_type,
                    cpu_req=spec.cpu_req,
                    ram_req=spec.ram_req,
                    msd_req=spec.msd_req,
                    source_node=spec.source_node,
                    destination_node=spec.destination_node,
                    alert_flag=spec.alert_flag or spec.is_ddos_spike,
                    method_used=method_used,
                    hybrid_branch="",
                    vnf_name=f"{algorithm}-{scenario.name}-{step}" if accepted else "",
                    placement_node_id=v_place,
                    routing_node_id=v_route,
                    sid_count=spec.msd_req if accepted else 0,
                    reject_reason="" if accepted else reject_reason,
                    tags=dict(spec.tags),
                )
            )

        summary = summarize_records(
            algorithm=algorithm,
            scenario=scenario.name,
            title=scenario.title,
            records=records,
            msd_drop_delta=0,
            final_active_vnfs=len(state_manager.as_public_dict().get("active_vnfs") or []),
        )
        write_records_csv(output_dir / f"{scenario.name}_{algorithm}_records.csv", records)
        return records, summary

    @staticmethod
    def _greedy_choice(snapshot, spec) -> Tuple[int, int]:
        state = snapshot.state
        best_node = None
        best_free_cpu = -1.0
        for node in range(len(snapshot.node_names)):
            free_cpu = 100.0 - float(state[node, 0])
            if (
                free_cpu >= spec.cpu_req
                and float(state[node, 1]) + spec.ram_req <= 100.0
                and float(state[node, 2]) + spec.msd_req <= float(snapshot.msd_limits[node])
                and free_cpu > best_free_cpu
            ):
                best_node = node
                best_free_cpu = free_cpu
        if best_node is None:
            from src.ai.heuristic import HardConstraintError

            raise HardConstraintError("greedy_no_feasible_node")
        return int(best_node), int(best_node)
