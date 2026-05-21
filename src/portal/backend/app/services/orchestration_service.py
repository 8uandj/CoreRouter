import asyncio
import time
import requests
import logging
from typing import Dict, Any, List, Optional
from src.portal.backend.app.models.schemas import SFCRequest

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
    def __init__(self, orchestrator, controller, sdn_controller_url: str):
        self.orchestrator = orchestrator
        self.controller = controller
        self.sdn_controller_url = sdn_controller_url

    async def rollback(self, new_name: str, reason: str):
        """Cleanup failed migration attempt."""
        logger.warning(f"PHASE: ROLLBACK - Cleaning up {new_name} due to: {reason}")
        try:
            self.orchestrator.trigger_terminate(new_name)
        except Exception as e:
            logger.error(f"Rollback termination failed: {e}")

    async def make_before_break_sequence(
            self, old_name: str, new_name: str, file_name: str,
            target_location: str, request: SFCRequest,
            ai_node_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Full Phase 5/6 Orchestration: Decision → K8s → Polling → Translate → Steer.
        Phase 6 extensions:
          - nodeSelector injection via ai_node_id→K8s mapping
          - Control-plane Steering Overhead measurement
            (Thời gian Backend REST→Controller→P4 push rule.
             KHÔNG phải Data-plane latency — data-plane xảy ra ở tốc độ nano-giây
             khi rule được nạp xong. MBB đảm bảo Packet Loss = 0 trong suốt thời gian này.)
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
        make_result = self.orchestrator.trigger_migrate_single(
            old_deploy_name=old_name,
            new_deploy_name=new_name,
            file_name=file_name,
            target_location=target_location,
            node_hostname=k8s_hostname  # PHASE 6: pass nodeSelector target
        )
        if make_result.get("status") != "success":
            logger.error(f"MAKE phase failed: {make_result.get('message')}")
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
                logger.info(f"VNF {new_name} is READY. IP: {status.get('clusterIP')}")
                break
            await asyncio.sleep(2)
            attempts += 1
        
        if not endpoint_info:
            # RÀ SOÁT 1: Lỗ hổng Treo Hệ Thống -> Kích hoạt ROLLBACK
            logger.error(f"VERIFY phase TIMEOUT for {new_name}. Initiating ROLLBACK.")
            await self.rollback(new_name, "VNF_PROVISION_TIMEOUT")
            return {"status": "error", "message": "VNF_PROVISION_TIMEOUT"}

        # RÀ SOÁT 2: Trích xuất IP Động (Pod IP / ClusterIP)
        dynamic_ip = endpoint_info.get("clusterIP")
        node_port = next((p["nodePort"] for p in endpoint_info.get("ports", []) if p.get("nodePort")), 0)
        
        # 3. Dịch ra SRv6 (Translate): Chuyển IP động thành chuỗi SID
        # Sửa đổi: Sử dụng dynamic_ip nếu node_port không có (cho trong-cluster)
        suffix = f"{node_port:04x}" if node_port else dynamic_ip.split(":")[-1]
        target_sid = f"2001:db8:ffff:1::{suffix}"
        logger.info(f"PHASE: TRANSLATE - Dynamic Endpoint {dynamic_ip}:{node_port} -> SID: {target_sid}")

        # 4. Bắn lệnh Steer: Gọi API /steer của SDN Controller Phase 4
        # PHASE 6: Bắt đầu đồng hồ đo "Control-plane Steering Overhead"
        # ⚠️  LƯU Ý THUẬT NGỮ (quan trọng cho luận văn):
        #   Metric này đo thời gian REST request → Controller xử lý → P4 rule nạp xong.
        #   ĐÂY KHÔNG PHẢI Data-plane latency (data-plane forward ở tốc độ nano-giây).
        #   Trong suốt thời gian này, MBB đảm bảo old VNF vẫn phục vụ → Packet Loss = 0.
        steer_start_ts = time.perf_counter()
        logger.info(f"PHASE: STEER - Sending command to SDN Controller at {self.sdn_controller_url}")
        steer_payload = {
            "new_deploy": new_name,
            "new_rules": [
                {
                    "switch": "s1",
                    "type": "ipv6_route",
                    "prefix": "fc00:beef::1", 
                    "prefix_len": 128,
                    "dst_mac": "00:00:00:00:00:01",
                    "src_mac": "00:00:00:00:00:02",
                    "out_port": 1
                },
                {
                    "switch": "s1",
                    "type": "srv6_sid",
                    "sid": target_sid
                }
            ]
        }
        
        try:
            resp = requests.post(f"{self.sdn_controller_url}/steer", json=steer_payload, timeout=5)
            if resp.status_code != 202:
                logger.error(f"STEER initiation failed. Triggering ROLLBACK.")
                await self.rollback(new_name, "SDN_CONTROLLER_REJECTED")
                return {"status": "error", "message": "SDN_CONTROLLER_REJECTED"}
        except Exception as e:
            logger.error(f"STEER connection error: {e}. Triggering ROLLBACK.")
            await self.rollback(new_name, "SDN_CONTROLLER_UNREACHABLE")
            return {"status": "error", "message": "SDN_CONTROLLER_UNREACHABLE"}

        # RÀ SOÁT 2: Deadlock tại bước chờ STEER.
        # Chờ xác nhận từ Controller với Timeout nghiêm ngặt.
        steer_confirmed = False
        for _ in range(15): # 15 * 2s = 30s Timeout
            try:
                s_resp = requests.get(f"{self.sdn_controller_url}/steer/status", timeout=2)
                if s_resp.json().get("confirm_steer_done"):
                    steer_confirmed = True
                    break
            except Exception: pass
            await asyncio.sleep(2)

        # PHASE 6: Tính toán Control-plane Steering Overhead (ms)
        # = Thời gian từ lúc Backend gửi /steer REST request → confirm_steer_done
        cp_steering_overhead_ms = round((time.perf_counter() - steer_start_ts) * 1000, 2)

        if not steer_confirmed:
            # CHỈ THỊ 2: Kích hoạt trạng thái "Dangling VNF"
            logger.error(f"STEER confirmation TIMEOUT after {cp_steering_overhead_ms}ms. System in DANGLING_VNF state.")
            # KHÔNG gọi break_old_vnf, KHÔNG rollback (vì có thể switch đang update dở)
            return {
                "status": "warning", 
                "message": "DANGLING_VNF: Steer confirmation missing. Connectivity might be split.",
                "data": {
                    "new_vnf": new_name, "old_vnf": old_name,
                    "cp_steering_overhead_ms": cp_steering_overhead_ms
                }
            }

        # 5. BREAK: Xóa VNF cũ sau khi đã steer thành công (Zero-Downtime)
        logger.info(
            f"PHASE 6: Control-plane Steering Overhead = {cp_steering_overhead_ms} ms "
            f"(REST→Controller→P4 rule push). Data-plane forward ≈ nanoseconds. Packet Loss = 0 via MBB."
        )
        logger.info(f"PHASE: BREAK - confirm_steer_done=True. Deleting old VNF: {old_name}")
        break_result = self.orchestrator.break_old_vnf(old_name)
        
        return {
            "status": "success",
            "message": "Hybrid Orchestration Phase 5/6 sequence COMPLETED",
            "data": {
                "dynamic_endpoint": {"ip": dynamic_ip, "port": node_port},
                "sid_list": [target_sid],
                "steer_status": "CONFIRMED",
                "break_result": break_result,
                # PHASE 6 metrics — đúng thuật ngữ cho luận văn
                "cp_steering_overhead_ms": cp_steering_overhead_ms,  # Control-plane overhead
                "k8s_node_hostname": k8s_hostname or "auto",
                # Note: Data-plane forwarding latency ≈ ns (P4 hardware speed, không đo được ở đây)
            }
        }

    def get_orchestrator(self):
        return self.orchestrator

    def get_controller(self):
        return self.controller

    def get_k8s_hostname(self, ai_node_id: int) -> str:
        return get_k8s_hostname(ai_node_id)
