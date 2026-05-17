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
}


def total_msd_drops(snapshot: Dict[str, object]) -> int:
    total = 0
    for value in snapshot.values():
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


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
) -> ScenarioSummary:
    rows = list(records)
    generated = len(rows)
    accepted = sum(1 for row in rows if row.accepted)
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
    migration_triggers = sum(1 for row in rows if row.migration_status)
    successful_pipelines = sum(
        1 for row in rows
        if row.latest_pipeline_status.lower() == "succeeded"
    )
    return ScenarioSummary(
        algorithm=algorithm,
        scenario=scenario,
        title=title,
        generated_requests=generated,
        accepted=accepted,
        rejected=rejected,
        acceptance_rate=(accepted / generated * 100.0) if generated else 0.0,
        no_safe_rate=(no_safe / generated * 100.0) if generated else 0.0,
        constraint_reject_rate=(constraint_rejects / generated * 100.0) if generated else 0.0,
        msd_violation_rate=(msd_violations / generated * 100.0) if generated else 0.0,
        mean_decision_latency_ms=mean(latencies) if latencies else 0.0,
        p95_decision_latency_ms=percentile(latencies, 95.0),
        timeout_count=timeout_count,
        migration_triggers=migration_triggers,
        successful_migration_pipelines=successful_pipelines,
        msd_drop_delta=msd_drop_delta,
        mean_sid_count=mean(sid_counts) if sid_counts else 0.0,
        final_active_vnfs=final_active_vnfs,
    )
