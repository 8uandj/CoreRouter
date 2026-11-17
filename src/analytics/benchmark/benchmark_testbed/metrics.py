from __future__ import annotations

from statistics import mean
from typing import Dict, Iterable, List

from .models import RequestRecord, ScenarioSummary


SAFE_REJECT_REASONS = {
    "NO_SAFE_ACTION",
    "no_safe_action",
    "no_safe_action_mask_all_false",
    "no_candidate",
    "placement_node_full",
    "routing_node_full",
    "reserve_failed",
    "heuristic_no_feasible_placement",
    "heuristic_msd_or_capacity_route_failed",
    "resilience_no_safe_pair_available",
    "greedy_no_feasible_node",
    "cpu_capacity",
    "ram_capacity",
    "placement_capacity",
    "msd_violation",
    "stale_telemetry",
    "stale_state",
    "no_safe_action",
}


def total_msd_drops(snapshot: Dict[str, object]) -> int:
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError("MSD counter snapshot is empty or missing")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0
           for value in snapshot.values()):
        raise ValueError("MSD counter snapshot contains missing/invalid measurements")
    return sum(snapshot.values())


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = int(round((pct / 100.0) * (len(ordered) - 1)))
    return float(ordered[max(0, min(rank, len(ordered) - 1))])


def summarize_records(
    algorithm: str,
    scenario: str,
    title: str,
    records: Iterable[RequestRecord],
    msd_drop_delta: int,
    final_active_vnfs: int,
    wall_clock_s: float,
) -> ScenarioSummary:
    rows = list(records)
    generated = len(rows)
    accepted = sum(1 for row in rows if row.accepted)
    admitted = sum(1 for row in rows if row.admitted)
    safe_admitted = sum(1 for row in rows if row.safe_admitted)
    deployed = sum(1 for row in rows if row.deployed)
    actuation_requested = sum(1 for row in rows if row.actuation_requested)
    rejected = generated - accepted
    timeout_count = sum(1 for row in rows if row.reject_reason == "timeout")
    no_safe = sum(1 for row in rows if row.reject_reason in SAFE_REJECT_REASONS)
    constraint_rejects = sum(
        1 for row in rows
        if (not row.accepted and row.reject_reason in SAFE_REJECT_REASONS)
    )
    msd_violations = sum(1 for row in rows if row.msd_violation)
    latencies = [row.decision_latency_ms for row in rows if row.reject_reason != "timeout"]
    sid_counts = [row.sid_count for row in rows if row.accepted]
    service_latencies = [row.service_latency_ms for row in rows if row.accepted and row.service_latency_ms > 0]
    component_values: Dict[str, List[float]] = {}
    for row in rows:
        for key, value in row.timing_ms.items():
            component_values.setdefault(key, []).append(float(value))
    component_percentiles = {
        key: {
            "p50": percentile(values, 50.0),
            "p95": percentile(values, 95.0),
            "p99": percentile(values, 99.0),
        }
        for key, values in component_values.items()
    }
    hourly_groups: Dict[int, List[RequestRecord]] = {}
    for row in rows:
        hourly_groups.setdefault(int(row.hour_index), []).append(row)
    hourly_summaries = []
    for hour, hour_rows in sorted(hourly_groups.items()):
        hour_latencies = [row.decision_latency_ms for row in hour_rows]
        hourly_summaries.append({
            "hour_index": hour,
            "generated_requests": len(hour_rows),
            "admitted": sum(row.admitted for row in hour_rows),
            "safe_admitted": sum(row.safe_admitted for row in hour_rows),
            "deployed": sum(row.deployed for row in hour_rows),
            "rejected": sum(not row.admitted for row in hour_rows),
            "decision_p50_ms": percentile(hour_latencies, 50.0),
            "decision_p95_ms": percentile(hour_latencies, 95.0),
            "decision_p99_ms": percentile(hour_latencies, 99.0),
        })
    migration_triggers = sum(1 for row in rows if row.migration_status == "triggered")
    readiness_waits = [row.deployment_wait_s for row in rows if row.actuation_requested and row.readiness_status != "not_waited"]
    successful_pipelines = sum(
        1 for row in rows
        if row.migration_completed
    )
    return ScenarioSummary(
        algorithm=algorithm,
        scenario=scenario,
        title=title,
        generated_requests=generated,
        accepted=accepted,
        admitted=admitted,
        safe_admitted=safe_admitted,
        deployed=deployed,
        actuation_requested=actuation_requested,
        rejected=rejected,
        acceptance_rate=(accepted / generated * 100.0) if generated else 0.0,
        no_safe_rate=(no_safe / generated * 100.0) if generated else 0.0,
        constraint_reject_rate=(constraint_rejects / generated * 100.0) if generated else 0.0,
        msd_violation_rate=(msd_violations / generated * 100.0) if generated else 0.0,
        mean_decision_latency_ms=mean(latencies) if latencies else 0.0,
        p95_decision_latency_ms=percentile(latencies, 95.0),
        timeout_count=timeout_count,
        mean_service_latency_ms=mean(service_latencies) if service_latencies else 0.0,
        migration_triggers=migration_triggers,
        successful_migration_pipelines=successful_pipelines,
        completed_migrations=successful_pipelines,
        msd_drop_delta=msd_drop_delta,
        mean_sid_count=mean(sid_counts) if sid_counts else 0.0,
        final_active_vnfs=final_active_vnfs,
        p50_decision_latency_ms=percentile(latencies, 50.0),
        p99_decision_latency_ms=percentile(latencies, 99.0),
        wall_clock_s=wall_clock_s,
        completed_ops_per_s=(generated / wall_clock_s) if wall_clock_s > 0 else 0.0,
        component_latency_percentiles_ms=component_percentiles,
        mean_migration_wait_s=mean([r.migration_wait_s for r in rows if r.migration_status == "triggered"]) if any(r.migration_status == "triggered" for r in rows) else 0.0,
        mean_deployment_readiness_wait_s=mean(readiness_waits) if readiness_waits else 0.0,
        hourly_summaries=hourly_summaries,
    )
