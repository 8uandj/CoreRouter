from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Dict, List, Tuple

from .config import BenchmarkConfig
from .exporters import write_records_csv
from .http_client import TestbedClient
from .metrics import summarize_records, total_msd_drops
from .models import ActiveReservation, RequestRecord, ScenarioDefinition


class ScenarioRunner:
    def __init__(self, config: BenchmarkConfig, client: TestbedClient) -> None:
        self.config = config
        self.client = client

    def run(self, scenario: ScenarioDefinition, output_dir: Path) -> Tuple[List[RequestRecord], object]:
        if self.config.reset_before_scenario:
            self.client.reset()
            self.client.set_alert(False)

        before_drops = self._read_msd_drop_total()
        rng = random.Random(self.config.seed + stable_name_offset(scenario.name))
        records: List[RequestRecord] = []
        active: List[ActiveReservation] = []
        steps = self.config.steps or scenario.default_steps

        for step in range(steps):
            active = self._expire_reservations(step, active)
            spec = scenario.request_factory(step, steps, rng)
            if spec is None:
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

            if record.migration_status and self.config.wait_for_migration:
                wait_s, pipeline = self._wait_for_idle()
                record.migration_wait_s = wait_s
                record.latest_pipeline_name = str(pipeline.get("name", ""))
                record.latest_pipeline_status = str(pipeline.get("overallStatus", ""))

            records.append(record)

        if self.config.cleanup_after_scenario:
            self._cleanup_reservations(active)
            self.client.set_alert(False)

        after_drops = self._read_msd_drop_total()
        _, state_body, _ = self.client.state()
        final_active_vnfs = len((state_body.get("data") or {}).get("active_vnfs") or [])
        summary = summarize_records(
            algorithm="hybrid_runtime",
            scenario=scenario.name,
            title=scenario.title,
            records=records,
            msd_drop_delta=max(0, after_drops - before_drops),
            final_active_vnfs=final_active_vnfs,
        )

        write_records_csv(output_dir / f"{scenario.name}_records.csv", records)
        if self.config.cleanup_after_scenario:
            self.client.reset()
            self.client.set_alert(False)
        return records, summary

    def _expire_reservations(
        self,
        step: int,
        active: List[ActiveReservation],
    ) -> List[ActiveReservation]:
        remaining: List[ActiveReservation] = []
        for reservation in active:
            if reservation.expire_step <= step:
                self._free_reservation(reservation)
            else:
                remaining.append(reservation)
        return remaining

    def _cleanup_reservations(self, active: List[ActiveReservation]) -> None:
        for reservation in active:
            self._free_reservation(reservation)

    def _free_reservation(self, reservation: ActiveReservation) -> None:
        self.client.free(
            {
                "v_place": reservation.v_place,
                "v_route": reservation.v_route,
                "cpu_req": reservation.cpu_req,
                "ram_req": reservation.ram_req,
                "msd_req": reservation.msd_req,
            }
        )

    def _read_msd_drop_total(self) -> int:
        status_code, body, _ = self.client.msd_drops()
        if status_code != 200:
            return 0
        return total_msd_drops(body)

    def _wait_for_idle(self) -> Tuple[float, Dict[str, object]]:
        start = time.perf_counter()
        latest_pipeline: Dict[str, object] = {}
        while (time.perf_counter() - start) < self.config.migration_timeout_s:
            _, body, _ = self.client.status()
            latest_pipeline = body.get("latest_pipeline") or {}
            if not body.get("is_migrating"):
                break
            time.sleep(self.config.poll_interval_s)
        return time.perf_counter() - start, latest_pipeline

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

        reject_reason = ""
        if not accepted:
            reject_reason = str(detail.get("code") or detail.get("message") or body.get("detail") or "request_failed")

        return RequestRecord(
            algorithm="hybrid_runtime",
            scenario=scenario_name,
            step=step,
            accepted=accepted,
            status_code=status_code,
            decision_latency_ms=round(latency_ms, 3),
            service_type=spec.service_type,
            cpu_req=spec.cpu_req,
            ram_req=spec.ram_req,
            msd_req=spec.msd_req,
            source_node=spec.source_node,
            destination_node=spec.destination_node,
            alert_flag=spec.alert_flag or spec.is_ddos_spike,
            method_used=str(data.get("method_used", "")) if isinstance(data, dict) else "",
            hybrid_branch=str(data.get("hybrid_branch", "")) if isinstance(data, dict) else "",
            vnf_name=str(data.get("vnf_name", "")) if isinstance(data, dict) else "",
            placement_node_id=placement.get("id") if isinstance(placement, dict) else None,
            placement_node_name=str(placement.get("name", "")) if isinstance(placement, dict) else "",
            routing_node_id=routing.get("id") if isinstance(routing, dict) else None,
            routing_node_name=str(routing.get("name", "")) if isinstance(routing, dict) else "",
            sid_count=len(sid_stack) if isinstance(sid_stack, list) else 0,
            reject_reason=reject_reason,
            migration_status=str(migration.get("status", "")) if isinstance(migration, dict) else "",
            migration_old_vnf=str(migration.get("old_vnf", "")) if isinstance(migration, dict) else "",
            migration_new_vnf=str(migration.get("new_vnf", "")) if isinstance(migration, dict) else "",
            tags=dict(spec.tags),
        )


def stable_name_offset(name: str) -> int:
    return sum(ord(ch) for ch in name)
