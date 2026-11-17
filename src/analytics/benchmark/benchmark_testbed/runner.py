from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from .config import BenchmarkConfig
from .exporters import write_hourly_summary_csv, write_records_csv
from .http_client import TestbedClient
from .latency_model import modeled_service_latency_ms
from .metrics import summarize_records, total_msd_drops
from .models import ActiveReservation, RequestRecord, ScenarioDefinition


class ScenarioRunner:
    def __init__(self, config: BenchmarkConfig, client: TestbedClient) -> None:
        self.config = config
        self.client = client

    def run(self, scenario: ScenarioDefinition, output_dir: Path) -> Tuple[List[RequestRecord], object]:
        if self.config.reset_before_scenario:
            reset_status, _, _ = self.client.reset()
            if reset_status != 200:
                raise RuntimeError("Testbed reset refused/unavailable; reconcile live allocations before running")
            self.client.set_alert(False)

        before_counters = self._read_msd_counters()
        before_drops = total_msd_drops(before_counters)
        rng = random.Random(self.config.seed + stable_name_offset(scenario.name))
        records: List[RequestRecord] = []
        active: List[ActiveReservation] = []
        steps = self.config.steps or scenario.default_steps
        if self.config.duration_hours > 0:
            steps = max(steps, 1_000_000_000)
        run_start = time.perf_counter()

        step = 0
        while step < steps and (
            self.config.duration_hours <= 0
            or time.perf_counter() - run_start < self.config.duration_hours * 3600.0
        ):
            iteration_start = time.perf_counter()
            active = self._expire_reservations(step, active)
            spec = scenario.request_factory(step, steps, rng)
            if spec is None:
                step += 1
                continue

            status_code, body, latency_ms = self.client.orchestrate(spec.to_payload())
            record = self._build_record(scenario.name, step, spec, status_code, body, latency_ms)

            if record.accepted and record.placement_node_id is not None and record.routing_node_id is not None:
                active.append(
                    ActiveReservation(
                        expire_step=step + spec.ttl_steps,
                        v_place=record.placement_node_id,
                        v_route=record.routing_node_id,
                        cpu_req=spec.cpu_req,
                        ram_req=spec.ram_req,
                        msd_req=record.sid_count or spec.msd_req,
                        vnf_name=record.vnf_name,
                    )
                )

            if record.actuation_requested and self.config.wait_for_migration:
                if record.migration_status == "triggered":
                    wait_s, outcome = self._wait_for_migration(
                        record.migration_old_vnf, record.migration_new_vnf or record.vnf_name)
                    record.migration_wait_s = wait_s
                    details = outcome.get("data") or {}
                    record.migration_completed = outcome.get("completion_verified") is True
                    record.migration_operation_id = str(details.get("steer_operation_id", ""))
                    record.migration_recovery_state = str(details.get("recovery_state", "UNKNOWN"))
                ready_wait, ready = self._wait_for_vnf_ready(
                    record.vnf_name, self.config.migration_timeout_s
                )
                record.deployment_wait_s = ready_wait
                record.deployed = ready
                record.readiness_status = "ready" if ready else "timeout_or_not_found"
                if ready:
                    record.deployment_status = "ready"
            elif record.actuation_requested:
                record.readiness_status = "not_waited"

            record.elapsed_s = max(0.0, time.perf_counter() - run_start)
            record.hour_index = int(record.elapsed_s // 3600.0)
            record.timestamp_utc = datetime.now(timezone.utc).isoformat()
            records.append(record)
            step += 1
            if self.config.request_interval_s > 0:
                time.sleep(max(0.0, self.config.request_interval_s - (time.perf_counter() - iteration_start)))

        wall_clock_s = max(0.0, time.perf_counter() - run_start)

        if self.config.cleanup_after_scenario:
            self._cleanup_reservations(active)
            self.client.set_alert(False)

        # Preserve raw request evidence even if the final counter read fails.
        write_records_csv(output_dir / f"{scenario.name}_records.csv", records)
        write_hourly_summary_csv(output_dir / f"{scenario.name}_hourly_summary.csv", records)
        after_counters = self._read_msd_counters()
        if set(after_counters) != set(before_counters):
            raise RuntimeError("MSD counter switch coverage changed during run")
        if any(after_counters[name] < value for name, value in before_counters.items()):
            raise RuntimeError("MSD counter decreased/reset during run")
        after_drops = total_msd_drops(after_counters)
        if after_drops < before_drops:
            raise RuntimeError("MSD counters decreased/reset during run; drop delta is not valid")
        _, state_body, _ = self.client.state()
        final_active_vnfs = len((state_body.get("data") or {}).get("active_vnfs") or [])
        summary = summarize_records(
            algorithm="hybrid_runtime",
            scenario=scenario.name,
            title=scenario.title,
            records=records,
            msd_drop_delta=after_drops - before_drops,
            final_active_vnfs=final_active_vnfs,
            wall_clock_s=wall_clock_s,
        )

        # Never hide unresolved live allocations by resetting the local ledger.
        return records, summary

    def _expire_reservations(
        self,
        step: int,
        active: List[ActiveReservation],
    ) -> List[ActiveReservation]:
        remaining: List[ActiveReservation] = []
        for reservation in active:
            if reservation.expire_step > step or not self._free_reservation(reservation):
                remaining.append(reservation)
        return remaining

    def _cleanup_reservations(self, active: List[ActiveReservation]) -> None:
        for reservation in active:
            self._free_reservation(reservation)

    def _free_reservation(self, reservation: ActiveReservation) -> bool:
        status, body, _ = self.client.free(
            {
                "vnf_name": reservation.vnf_name or None,
                "v_place": reservation.v_place,
                "v_route": reservation.v_route,
                "cpu_req": reservation.cpu_req,
                "ram_req": reservation.ram_req,
                "msd_req": reservation.msd_req,
            }
        )

        return status == 200 and body.get("status") == "success"

    def _read_msd_drop_total(self) -> int:
        return total_msd_drops(self._read_msd_counters())

    def _read_msd_counters(self) -> Dict[str, int]:
        status_code, body, _ = self.client.msd_drops()
        if status_code != 200:
            raise RuntimeError("MSD counter endpoint unavailable; cannot certify drop measurements")
        total_msd_drops(body)
        return dict(body)

    def _wait_for_migration(self, old_name: str, new_name: str) -> Tuple[float, Dict[str, object]]:
        start = time.perf_counter()
        operation_id = None
        while (time.perf_counter() - start) < self.config.migration_timeout_s:
            status, body, _ = self.client.migration_status(new_name)
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            if status == 200 and data.get("new_vnf") == new_name and data.get("old_vnf") == old_name:
                observed_id = data.get("steer_operation_id")
                if observed_id:
                    if operation_id is not None and operation_id != observed_id:
                        return time.perf_counter() - start, {
                            "status": "warning", "completion_verified": False,
                            "data": {**data, "recovery_state": "JOURNAL_OPERATION_CHANGED"}}
                    operation_id = observed_id
                if body.get("status") in {"success", "warning", "error"}:
                    completed = (body.get("status") == "success"
                        and data.get("recovery_state") == "COMPLETED"
                        and data.get("steer_status") == "CONFIRMED"
                        and isinstance(operation_id, str) and bool(operation_id)
                        and observed_id == operation_id)
                    return time.perf_counter() - start, {**body, "completion_verified": completed}
            time.sleep(self.config.poll_interval_s)
        return time.perf_counter() - start, {
            "status": "warning", "completion_verified": False,
            "data": {"old_vnf": old_name, "new_vnf": new_name,
                     "steer_operation_id": operation_id or "", "recovery_state": "JOURNAL_TIMEOUT"}}

    def _wait_for_vnf_ready(self, vnf_name: str, timeout_s: float) -> Tuple[float, bool]:
        start = time.perf_counter()
        ready = False
        while (time.perf_counter() - start) < timeout_s:
            status_code, body, _ = self.client.state()
            state = body.get("data") if status_code == 200 and isinstance(body.get("data"), dict) else {}
            active = state.get("active_vnfs") or []
            ready = any(
                isinstance(vnf, dict)
                and vnf.get("name") == vnf_name
                and vnf.get("deployment_ready") is True
                and not bool(vnf.get("presence_unconfirmed", False))
                for vnf in active
            )
            if ready:
                break
            time.sleep(self.config.poll_interval_s)
        return time.perf_counter() - start, ready

    def _build_record(
        self,
        scenario_name: str,
        step: int,
        spec,
        status_code: int,
        body: Dict[str, object],
        latency_ms: float,
    ) -> RequestRecord:
        accepted = status_code == 200 and body.get("status") == "success"
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
        placement = data.get("placement_node") if isinstance(data, dict) else {}
        routing = data.get("routing_node") if isinstance(data, dict) else {}
        migration = data.get("migration_result") if isinstance(data, dict) else None
        sid_stack = data.get("srv6_segment_list") if isinstance(data, dict) else []
        state = data.get("state") if isinstance(data.get("state"), dict) else {}

        reject_reason = ""
        if not accepted:
            reject_reason = str(
                detail.get("reason_key")
                or detail.get("code")
                or detail.get("message")
                or body.get("message")
                or body.get("detail")
                or "request_failed"
            )

        placement_id = placement.get("id") if isinstance(placement, dict) else None
        routing_id = routing.get("id") if isinstance(routing, dict) else None
        sid_count = len(sid_stack) if isinstance(sid_stack, list) else 0
        service_latency = 0.0
        if accepted and placement_id is not None and routing_id is not None:
            cpu_utils = {
                int(node.get("id")): float(node.get("cpu_util", 0.0)) / 100.0
                for node in state.get("nodes", [])
                if isinstance(node, dict) and node.get("id") is not None
            }
            service_latency = modeled_service_latency_ms(
                placement_id,
                routing_id,
                sid_count or spec.msd_req,
                cpu_utils.get(int(placement_id), 0.0),
                cpu_utils.get(int(routing_id), 0.0),
            )

        return RequestRecord(
            algorithm="hybrid_runtime",
            scenario=scenario_name,
            step=step,
            accepted=accepted,
            status_code=status_code,
            decision_latency_ms=round(latency_ms, 3),
            service_latency_ms=round(service_latency, 3),
            service_type=spec.service_type,
            cpu_req=spec.cpu_req,
            ram_req=spec.ram_req,
            msd_req=spec.msd_req,
            source_node=spec.source_node,
            destination_node=spec.destination_node,
            alert_flag=spec.alert_flag or spec.is_ddos_spike,
            admitted=accepted,
            safe_admitted=accepted,
            deployed=False,
            actuation_requested=bool(migration),
            deployment_status=str(migration.get("status", "not_requested")) if isinstance(migration, dict) else "not_requested",
            method_used=str(data.get("method_used", "")) if isinstance(data, dict) else "",
            hybrid_branch=str(data.get("hybrid_branch", "")) if isinstance(data, dict) else "",
            vnf_name=str(data.get("vnf_name", "")) if isinstance(data, dict) else "",
            placement_node_id=placement_id,
            placement_node_name=str(placement.get("name", "")) if isinstance(placement, dict) else "",
            routing_node_id=routing_id,
            routing_node_name=str(routing.get("name", "")) if isinstance(routing, dict) else "",
            sid_count=sid_count,
            msd_violation=reject_reason == "msd_violation",
            reject_reason=reject_reason,
            migration_status=str(migration.get("status", "")) if isinstance(migration, dict) else "",
            migration_old_vnf=str(migration.get("old_vnf", "")) if isinstance(migration, dict) else "",
            migration_new_vnf=str(migration.get("new_vnf", "")) if isinstance(migration, dict) else "",
            timing_ms={
                str(key): float(value)
                for key, value in (data.get("timings_ms") or {}).items()
                if isinstance(value, (int, float))
            } if isinstance(data, dict) else {},
            tags=dict(spec.tags),
        )


def stable_name_offset(name: str) -> int:
    return sum(ord(ch) for ch in name)
