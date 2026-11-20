from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class RequestSpec:
    service_type: str
    cpu_req: float
    ram_req: float
    msd_req: int
    source_node: Optional[int] = None
    destination_node: Optional[int] = None
    alert_flag: bool = False
    is_ddos_spike: bool = False
    ttl_steps: int = 30
    tags: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "service_type": self.service_type,
            "cpu_req": self.cpu_req,
            "ram_req": self.ram_req,
            "msd_req": self.msd_req,
            "alert_flag": self.alert_flag,
            "is_ddos_spike": self.is_ddos_spike,
        }
        if self.source_node is not None:
            payload["source_node"] = self.source_node
        if self.destination_node is not None:
            payload["destination_node"] = self.destination_node
        return payload


@dataclass(frozen=True)
class ActiveReservation:
    expire_step: int
    v_place: int
    v_route: int
    cpu_req: float
    ram_req: float
    msd_req: int
    vnf_name: str


@dataclass
class RequestRecord:
    algorithm: str
    scenario: str
    step: int
    accepted: bool
    status_code: int
    decision_latency_ms: float
    service_latency_ms: float
    service_type: str
    cpu_req: float
    ram_req: float
    msd_req: int
    source_node: Optional[int]
    destination_node: Optional[int]
    alert_flag: bool
    admitted: bool = False
    safe_admitted: bool = False
    deployed: bool = False
    actuation_requested: bool = False
    deployment_status: str = "not_requested"
    deployment_wait_s: float = 0.0
    readiness_status: str = "not_checked"
    method_used: str = ""
    hybrid_branch: str = ""
    vnf_name: str = ""
    placement_node_id: Optional[int] = None
    placement_node_name: str = ""
    routing_node_id: Optional[int] = None
    routing_node_name: str = ""
    sid_count: int = 0
    msd_violation: bool = False
    reject_reason: str = ""
    migration_status: str = ""
    migration_old_vnf: str = ""
    migration_new_vnf: str = ""
    migration_completed: bool = False
    migration_operation_id: str = ""
    migration_recovery_state: str = ""
    migration_wait_s: float = 0.0
    latest_pipeline_name: str = ""
    latest_pipeline_status: str = ""
    timing_ms: Dict[str, float] = field(default_factory=dict)
    elapsed_s: float = 0.0
    hour_index: int = 0
    timestamp_utc: str = ""
    tags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioSummary:
    algorithm: str
    scenario: str
    title: str
    generated_requests: int
    accepted: int
    admitted: int
    safe_admitted: int
    deployed: int
    actuation_requested: int
    rejected: int
    acceptance_rate: float
    no_safe_rate: float
    constraint_reject_rate: float
    msd_violation_rate: float
    mean_decision_latency_ms: float
    p95_decision_latency_ms: float
    timeout_count: int
    mean_service_latency_ms: float
    migration_triggers: int
    successful_migration_pipelines: int
    msd_drop_delta: int
    mean_sid_count: float
    final_active_vnfs: int
    p50_decision_latency_ms: float = 0.0
    p99_decision_latency_ms: float = 0.0
    wall_clock_s: float = 0.0
    completed_ops_per_s: float = 0.0
    component_latency_percentiles_ms: Dict[str, Dict[str, float]] = field(default_factory=dict)
    mean_migration_wait_s: float = 0.0
    mean_deployment_readiness_wait_s: float = 0.0
    hourly_summaries: List[Dict[str, Any]] = field(default_factory=list)
    completed_migrations: int = 0
    notes: str = ""


RequestFactory = Callable[[int, int, "RandomLike"], Optional[RequestSpec]]


class RandomLike:
    """Protocol-sized helper to avoid importing typing.Protocol at runtime."""

    def random(self) -> float: ...
    def randint(self, a: int, b: int) -> int: ...
    def choice(self, seq: List[Any]) -> Any: ...


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    title: str
    description: str
    default_steps: int
    request_factory: RequestFactory
