import time
import requests
import logging
from typing import Dict, Any, List, Optional
from src.portal.backend.app.models.schemas import SFCRequest

logger = logging.getLogger("OrchestrationService")

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

    async def make_before_break_sequence(self, old_name: str, new_name: str, file_name: str, target_location: str, request: SFCRequest) -> Dict[str, Any]:
        """
        Full Phase 5 Orchestration: Decision -> K8s -> Polling -> Translate -> Steer.
        Includes Timeout and Rollback protection.
        """
        # 1. Kích hoạt K8s: Gọi Tekton để tạo Pod mới (MAKE phase)
        logger.info(f"PHASE: MAKE - Triggering Tekton for replacement VNF: {new_name} at {target_location}")
        make_result = self.orchestrator.trigger_migrate_single(
            old_deploy_name=old_name,
            new_deploy_name=new_name,
            file_name=file_name,
            target_location=target_location
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
            time.sleep(2)
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
        for _ in range(15): # 15 * 2s = 30s Timeout (theo yêu cầu chỉ thị Phase 5)
            try:
                s_resp = requests.get(f"{self.sdn_controller_url}/steer/status", timeout=2)
                if s_resp.json().get("confirm_steer_done"):
                    steer_confirmed = True
                    break
            except Exception: pass
            time.sleep(2)

        if not steer_confirmed:
            # CHỈ THỊ 2: Kích hoạt trạng thái "Dangling VNF"
            logger.error("STEER confirmation TIMEOUT. System in DANGLING_VNF state. Keeping old VNF.")
            # KHÔNG gọi break_old_vnf, KHÔNG rollback (vì có thể switch đang update dở)
            return {
                "status": "warning", 
                "message": "DANGLING_VNF: Steer confirmation missing. Connectivity might be split. Manual check required.",
                "data": {"new_vnf": new_name, "old_vnf": old_name}
            }

        # 5. BREAK: Xóa VNF cũ sau khi đã steer thành công (Zero-Downtime)
        logger.info(f"PHASE: BREAK - confirm_steer_done=True. Deleting old VNF: {old_name}")
        break_result = self.orchestrator.break_old_vnf(old_name)
        
        return {
            "status": "success",
            "message": "Hybrid Orchestration Phase 5 sequence COMPLETED",
            "data": {
                "dynamic_endpoint": {"ip": dynamic_ip, "port": node_port},
                "sid_list": [target_sid],
                "steer_status": "CONFIRMED",
                "break_result": break_result
            }
        }

    def get_orchestrator(self):
        return self.orchestrator

    def get_controller(self):
        return self.controller
