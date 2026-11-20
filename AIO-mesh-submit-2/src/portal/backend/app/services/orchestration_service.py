from __future__ import annotations

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from src.core.state_manager import get_state_manager
from .migration_journal import MigrationJournal
from .vnf_service_type import resolve_vnf_service
from .realization import AdmittedRealization, validate_realization_payload

logger = logging.getLogger("OrchestrationService")

# =============================================================================
# PHASE 6: AI → K8s Node Mapping Dictionary
# =============================================================================
# Theorem Backbone (from thesis Table 4.1):
#   Node 0 = Hanoi        (Core, CPU=200, MSD=10)  → k8s-master
#   Node 1 = Hai Phong    (Core, CPU=150, MSD=10)  → k8s-master
#   Node 2 = Ninh Binh    (Edge, CPU=80,  MSD=5)   → k8s-master
#   Node 3 = Vinh         (Edge, CPU=80,  MSD=5)   → worker1
#   Node 4 = Hue          (Edge, CPU=60,  MSD=4)   → worker1
#   Node 5 = Da Nang      (Core, CPU=150, MSD=8)   → worker1
#   Node 6 = Quy Nhon     (Edge, CPU=60,  MSD=4)   → worker2
#   Node 7 = Nha Trang    (Edge, CPU=80,  MSD=5)   → worker2
#   Node 8 = Ho Chi Minh  (Core, CPU=200, MSD=10)  → worker2
#   Node 9 = Can Tho      (Edge, CPU=80,  MSD=5)   → worker2
#
# Mapping logic: North cluster (3 nodes) → k8s-master
#                Central cluster (3 nodes) → worker1
#                South cluster (4 nodes)  → worker2
AI_NODE_TO_K8S_HOSTNAME: Dict[int, str] = {
    0: "k8s-master",   # Hà Nội
    1: "k8s-master",   # Hải Phòng
    2: "k8s-master",   # Ninh Bình
    3: "worker1",      # Vinh
    4: "worker1",      # Huế
    5: "worker1",      # Đà Nẵng
    6: "worker2",      # Quy Nhơn
    7: "worker2",      # Nha Trang
    8: "worker2",      # Hồ Chí Minh
    9: "worker2",      # Cần Thơ
}

def get_k8s_hostname(ai_node_id: int) -> str:
    """Translate JO-VPPM node index to K8s physical hostname."""
    hostname = AI_NODE_TO_K8S_HOSTNAME.get(int(ai_node_id), "")
    if not hostname:
        logger.warning(f"AI node {ai_node_id} has no K8s mapping. Floating placement.")
    return hostname

class OrchestrationService:
    def __init__(self, orchestrator, controller, sdn_controller_url: str,
                 state_manager=None, rollback_timeout_s: float = 30.0,
                 rollback_poll_s: float = 1.0, migration_journal=None):
        self.orchestrator = orchestrator
        self.controller = controller
        self.sdn_controller_url = sdn_controller_url
        self.state_manager = state_manager or get_state_manager()
        self.migration_journal = migration_journal or MigrationJournal()
        self.rollback_timeout_s = float(rollback_timeout_s)
        self.rollback_poll_s = float(rollback_poll_s)
        if self.rollback_timeout_s <= 0 or self.rollback_poll_s <= 0:
            raise ValueError("rollback wait durations must be positive")

    async def _wait_for_replacement_absence(self, new_name: str) -> bool:
        """Only release a failed replacement reservation after deletion is observed."""
        check_presence = getattr(self.orchestrator, "deployment_presence", None)
        if not callable(check_presence):
            logger.warning("Cannot confirm replacement absence; retaining reservation for %s", new_name)
            return False
        deadline = time.monotonic() + self.rollback_timeout_s
        while time.monotonic() < deadline:
            try:
                present = check_presence(new_name)
            except Exception:
                logger.exception("Could not verify replacement presence for %s", new_name)
                present = None
            if present is False:
                return True
            await asyncio.sleep(min(self.rollback_poll_s, max(0.0, deadline - time.monotonic())))
        return False

    async def rollback(self, new_name: str, reason: str):
        """Cleanup failed migration attempt."""
        logger.warning(f"PHASE: ROLLBACK - Cleaning up {new_name} due to: {reason}")
        try:
            result = self.orchestrator.trigger_terminate(new_name)
            if not isinstance(result, dict) or result.get("status") != "success":
                logger.error("Termination was not accepted for %s: %s", new_name, result)
            absent = await self._wait_for_replacement_absence(new_name)
            if absent:
                self.state_manager.release_resources(new_name)
            else:
                logger.error("Replacement %s still present/unverified; retaining its reservation", new_name)
        except Exception as e:
            logger.error(f"Rollback termination failed: {e}")

    def get_migration_status(self, replacement: str):
        return self.migration_journal.get(replacement)

    async def make_before_break_sequence(self, old_name, new_name, file_name,
                                         target_location, request, ai_node_id=None,
                                         admitted_realization=None):
        if (not isinstance(admitted_realization, AdmittedRealization)
                or admitted_realization.forwarding_sid is None):
            return {"status": "error", "code": "UNSUPPORTED_ADMITTED_REALIZATION",
                    "message": "No verified admission-to-forwarding realization is available.",
                    "data": {"old_vnf": old_name, "new_vnf": new_name,
                             "recovery_state": "REALIZATION_REJECTED"}}
        # Persist before any infrastructure mutation. A journal failure here
        # stops execution rather than create an untracked background migration.
        started = self.migration_journal.start(new_name, {
            "status": "running", "data": {"old_vnf": old_name, "new_vnf": new_name,
                                            "recovery_state": "MAKE_STARTED"}})
        if not started:
            return {"status": "error", "message": "MIGRATION_ALREADY_EXISTS",
                    "data": {"new_vnf": new_name}}
        try:
            result = await self._execute_make_before_break(
                old_name, new_name, file_name, target_location, request, ai_node_id,
                admitted_realization)
        except Exception:
            logger.exception("Migration failed; retaining allocations pending reconciliation")
            previous = self.get_migration_status(new_name) or {}
            result = {"status": "warning", "message": "MIGRATION_UNCERTAIN",
                      "data": {**previous.get("data", {}),
                               "recovery_state": "MIGRATION_UNCERTAIN"}}
        except asyncio.CancelledError:
            previous = self.get_migration_status(new_name) or {}
            self.migration_journal.record(new_name, {
                "status": "warning", "message": "MIGRATION_CANCELLED",
                "data": {**previous.get("data", {}), "recovery_state": "MIGRATION_UNCERTAIN"}})
            raise
        result["data"] = {**result.get("data", {}), "old_vnf": old_name, "new_vnf": new_name}
        self.migration_journal.record(new_name, result)
        return result

    async def _execute_make_before_break(
            self, old_name: str, new_name: str, file_name: str,
            target_location: str, request: SFCRequest,
            ai_node_id: Optional[int] = None,
            admitted_realization: Optional[AdmittedRealization] = None) -> Dict[str, Any]:
        """
        Full Phase 5/6 Orchestration: Decision → K8s → Polling → Translate → Steer.
        Phase 6 extensions:
          - nodeSelector injection via ai_node_id→K8s mapping
          - Control-plane Steering Overhead measurement
            (Thời gian Backend REST→Controller→P4 push rule.
             Không đo data-plane latency hoặc packet loss.)
        Includes Timeout and Rollback protection.
        """
        # PHASE 6: Resolve K8s hostname from AI decision
        k8s_hostname = get_k8s_hostname(ai_node_id) if ai_node_id is not None else ""
        if k8s_hostname:
            logger.info(f"PHASE 6: AI node {ai_node_id} mapped to K8s hostname '{k8s_hostname}'")
        else:
            logger.info("PHASE 6: No AI node mapping — floating placement (scheduler decides)")

        # 1. Kích hoạt K8s: Gọi Tekton để tạo Pod mới (MAKE phase)
        logger.info(f"PHASE: MAKE - Triggering Tekton for replacement VNF: {new_name} at {target_location}")
        if old_name is None:
            vnf_type, _ = resolve_vnf_service(getattr(request, "service_type", "data"))
            make_result = self.orchestrator.trigger_deploy(
                name=new_name, vnf_type=vnf_type, profile="standard",
                location=target_location, node_hostname=k8s_hostname)
        else:
            make_result = self.orchestrator.trigger_migrate_single(
                old_deploy_name=old_name,
                new_deploy_name=new_name,
                file_name=file_name,
                target_location=target_location,
                node_hostname=k8s_hostname  # PHASE 6: pass nodeSelector target
            )
        if make_result.get("status") != "success":
            logger.error(f"MAKE phase failed: {make_result.get('message')}")
            if await self._wait_for_replacement_absence(new_name):
                self.state_manager.release_resources(new_name)
            else:
                logger.error("MAKE failure left replacement state uncertain; retaining reservation for %s", new_name)
            return make_result

        # 2. Lấy Endpoint Động: Polling với Timeout (QUY TẮC THÉP SỐ 3)
        logger.info(f"PHASE: VERIFY - Polling dynamic endpoint/readiness for {new_name}")
        endpoint_info = None
        attempts = 0
        max_attempts = 15 # 15 * 2s = 30s Timeout
        
        while attempts < max_attempts:
            status = self.orchestrator.get_replacement_endpoint(new_name)
            if status.get("isReady"):
                endpoint_info = status
                logger.info("VNF %s is READY. Pod IP: %s on %s",
                            new_name, status.get("podIP"), status.get("nodeName"))
                break
            await asyncio.sleep(2)
            attempts += 1
        
        if not endpoint_info:
            # RÀ SOÁT 1: Lỗ hổng Treo Hệ Thống -> Kích hoạt ROLLBACK
            logger.error(f"VERIFY phase TIMEOUT for {new_name}. Initiating ROLLBACK.")
            await self.rollback(new_name, "VNF_PROVISION_TIMEOUT")
            return {"status": "error", "message": "VNF_PROVISION_TIMEOUT"}

        # RÀ SOÁT 2: Trích xuất IP Động (Pod IP / ClusterIP)
        dynamic_ip = endpoint_info.get("podIP")
        node_port = next((p["nodePort"] for p in endpoint_info.get("ports", []) if p.get("nodePort")), 0)
        if not dynamic_ip:
            logger.error("VNF %s is marked Ready without a Pod IP; retaining both endpoints", new_name)
            return {"status": "warning", "message": "VNF_ENDPOINT_UNRESOLVED",
                    "data": {"old_vnf": old_name, "new_vnf": new_name,
                             "recovery_state": "VNF_ENDPOINT_UNRESOLVED"}}
        
        # The admitted SID is the terminal switch SID; the Pod IP remains the
        # inner IPv4 destination and is never fabricated into a SID.
        logger.info("PHASE: TRANSLATE - Ready endpoint %s:%s via terminal SID %s",
                    dynamic_ip, node_port, admitted_realization.forwarding_sid)

        # 4. Bắn lệnh Steer: Gọi API /steer của SDN Controller Phase 4
        # PHASE 6: Bắt đầu đồng hồ đo "Control-plane Steering Overhead"
        # ⚠️  LƯU Ý THUẬT NGỮ (quan trọng cho luận văn):
        #   Metric này đo thời gian REST request → Controller xử lý → P4 rule nạp xong.
        #   Đây là control-plane overhead; packet loss cần đo bằng packet traces.
        steer_start_ts = time.perf_counter()
        logger.info(f"PHASE: STEER - Sending command to SDN Controller at {self.sdn_controller_url}")
        steer_operation_id = admitted_realization.operation_id
        steer_payload = {
            "request_id": admitted_realization.request_id,
            "operation_id": steer_operation_id,
            "topology_hash": admitted_realization.topology_hash,
            "profile_id": admitted_realization.profile_id,
            "p4_topology_hash": admitted_realization.p4_topology_hash,
            "new_deploy": new_name,
            "switch_path": list(admitted_realization.switch_path),
            "sid_stack": list(admitted_realization.sid_stack),
        }
        try:
            validate_realization_payload(admitted_realization, steer_payload)
        except ValueError as exc:
            return {"status": "error", "code": "REALIZATION_REJECTED",
                    "message": str(exc),
                    "data": {"old_vnf": old_name, "new_vnf": new_name,
                             "recovery_state": "REALIZATION_REJECTED"}}
        
        self.migration_journal.record(new_name, {
            "status": "running", "data": {"old_vnf": old_name, "new_vnf": new_name,
                "steer_operation_id": steer_operation_id, "steer_payload": steer_payload,
                "recovery_state": "STEERING_SUBMITTING"}})
        submission_state = "accepted"
        try:
            import requests

            resp = requests.post(f"{self.sdn_controller_url}/steer", json=steer_payload, timeout=5)
            if resp.status_code != 202:
                submission_state = f"http_{resp.status_code}"
                logger.error("STEER submission returned %s; installation outcome uncertain", resp.status_code)
        except Exception:
            submission_state = "response_unavailable"
            logger.exception("STEER submission response unavailable; retaining both VNFs while checking status")

        # A lost response or error does not prove that no forwarding rules changed.
        # Poll the same operation; never terminate either endpoint on uncertainty.
        # RÀ SOÁT 2: Deadlock tại bước chờ STEER.
        # Chờ xác nhận từ Controller với Timeout nghiêm ngặt.
        steer_confirmed = False
        for _ in range(15): # 15 * 2s = 30s Timeout
            try:
                import requests

                s_resp = requests.get(f"{self.sdn_controller_url}/steer/status", timeout=2)
                status = s_resp.json()
                if (s_resp.status_code == 200
                        and status.get("confirm_steer_done") is True
                        and status.get("new_deploy") == new_name
                        and status.get("operation_id") == steer_operation_id
                        and status.get("request_id") == admitted_realization.request_id
                        and status.get("topology_hash") == admitted_realization.topology_hash
                        and status.get("profile_id") == admitted_realization.profile_id
                        and status.get("p4_topology_hash") == admitted_realization.p4_topology_hash):
                    steer_confirmed = True
                    break
            except Exception: pass
            await asyncio.sleep(2)

        # PHASE 6: Tính toán Control-plane Steering Overhead (ms)
        # = Thời gian từ lúc Backend gửi /steer REST request → confirm_steer_done
        cp_steering_overhead_ms = round((time.perf_counter() - steer_start_ts) * 1000, 2)

        if not steer_confirmed:
            # CHỈ THỊ 2: Kích hoạt trạng thái "Dangling VNF"
            logger.error(
                "STEERING_UNCERTAIN operation_id=%s old_vnf=%s new_vnf=%s submission=%s elapsed_ms=%s; retaining both endpoints",
                steer_operation_id, old_name, new_name, submission_state, cp_steering_overhead_ms,
            )
            # KHÔNG gọi break_old_vnf, KHÔNG rollback (vì có thể switch đang update dở)
            return {
                "status": "warning", 
                "message": "DANGLING_VNF: Steer confirmation missing. Connectivity might be split.",
                "data": {
                    "new_vnf": new_name, "old_vnf": old_name,
                    "cp_steering_overhead_ms": cp_steering_overhead_ms,
                    "steer_operation_id": steer_operation_id,
                    "steer_submission_state": submission_state,
                    "recovery_state": "STEERING_UNCERTAIN",
                }
            }

        # 5. BREAK: Xóa VNF cũ sau confirmation đúng operation.
        logger.info(
            f"PHASE 6: Control-plane Steering Overhead = {cp_steering_overhead_ms} ms "
            f"(REST→Controller confirmation). Packet loss and data-plane latency are not measured."
        )
        logger.info(f"PHASE: BREAK - confirm_steer_done=True. Deleting old VNF: {old_name}")
        recovery_data = {
            "old_vnf": old_name, "new_vnf": new_name,
            "steer_operation_id": steer_operation_id, "steer_status": "CONFIRMED",
            "recovery_state": "STEERED" if old_name is None else "BREAK_REQUESTING",
        }
        if old_name is None:
            return {
                "status": "success",
                "message": "VNF created, ready, and steered; no old VNF required BREAK.",
                "data": {
                    **recovery_data,
                    "dynamic_endpoint": {"ip": dynamic_ip, "port": node_port},
                    "sid_list": list(admitted_realization.sid_stack),
                    "switch_path": list(admitted_realization.switch_path),
                    "cp_steering_overhead_ms": cp_steering_overhead_ms,
                    "k8s_node_hostname": k8s_hostname or "auto",
                },
            }
        self.migration_journal.record(new_name, {"status": "running", "data": recovery_data})
        try:
            break_result = self.orchestrator.break_old_vnf(old_name)
        except Exception as exc:
            logger.exception("BREAK request failed for %s", old_name)
            break_result = {"status": "error", "message": str(exc)}
        if not isinstance(break_result, dict) or break_result.get("status") != "success":
            return {"status": "warning", "message": "BREAK_FAILED",
                    "data": {**recovery_data, "recovery_state": "BREAK_FAILED"}}
        if not await self._wait_for_replacement_absence(old_name):
            return {"status": "warning", "message": "BREAK_UNCONFIRMED",
                    "data": {**recovery_data, "recovery_state": "BREAK_UNCONFIRMED",
                             "break_result": break_result}}
        self.state_manager.release_resources(old_name)

        return {
            "status": "success",
            "message": "Hybrid Orchestration Phase 5/6 sequence COMPLETED",
            "data": {
                "old_vnf": old_name, "new_vnf": new_name,
                "recovery_state": "COMPLETED",
                "dynamic_endpoint": {"ip": dynamic_ip, "port": node_port},
                "sid_list": list(admitted_realization.sid_stack),
                "switch_path": list(admitted_realization.switch_path),
                "steer_status": "CONFIRMED",
                "steer_operation_id": steer_operation_id,
                "break_result": break_result,
                # PHASE 6 metrics — đúng thuật ngữ cho luận văn
                "cp_steering_overhead_ms": cp_steering_overhead_ms,  # Control-plane overhead
                "k8s_node_hostname": k8s_hostname or "auto",
                # Data-plane forwarding latency and packet loss require separate measurement.
            }
        }

    def get_orchestrator(self):
        return self.orchestrator

    def get_controller(self):
        return self.controller

    def get_k8s_hostname(self, ai_node_id: int) -> str:
        return get_k8s_hostname(ai_node_id)
