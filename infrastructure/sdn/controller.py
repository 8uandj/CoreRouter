"""
3S-COM Testbed — Phase 4: SDN Controller (P4Runtime gRPC)
==========================================================

QUY TẮC THÉP SỐ 3 — Make-Before-Break Steer:
  Controller chỉ được bắn lệnh gRPC bẻ luồng khi:
    1. K8s báo VNF mới đã Ready (Readiness probe pass)
    2. Sau khi steer xong → trả về confirm_steer_done: true
    3. Tekton nhận confirm_steer_done mới được phép BREAK (xoá VNF cũ)

Không BSID. Steer chỉ là cập nhật bảng routing_v6 + srv6_local_sid.
"""

import time
import json
import struct
import socket
import subprocess
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

# P4Runtime protobuf — optional, chỉ cần nếu dùng gRPC P4Runtime trực tiếp
# ThriftController (mode mặc định) KHÔNG cần grpc hay proto
try:
    import grpc
    import p4.v1.p4runtime_pb2       as p4rt_pb2
    import p4.v1.p4runtime_pb2_grpc  as p4rt_grpc
    import p4.config.v1.p4info_pb2   as p4info_pb2
    HAS_P4RUNTIME = True
except ImportError:
    HAS_P4RUNTIME = False

log = logging.getLogger("sdn.controller")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


# ══════════════════════════════════════════════════════════════
#  Data structures
# ══════════════════════════════════════════════════════════════

class SteerState(Enum):
    IDLE         = "idle"
    MAKING       = "making"      # VNF mới đang tạo
    WAITING_READY = "waiting_ready"
    STEERING     = "steering"    # đang gửi gRPC xuống switch
    DONE         = "done"        # confirm_steer_done = True
    FAILED       = "failed"

@dataclass
class SwitchConn:
    name:       str
    grpc_port:  int
    device_id:  int
    p4info_path: str
    json_path:  str
    channel:    object = field(default=None, repr=False)
    stub:       object = field(default=None, repr=False)
    connected:  bool   = False

@dataclass
class ForwardingRule:
    """Một entry trong bảng routing_v6 hoặc srv6_local_sid."""
    table_name:  str
    match_field: str      # tên field match (e.g. "hdr.ipv6.dstAddr")
    match_value: str      # giá trị (IPv6 prefix hoặc địa chỉ)
    match_type:  str      # "lpm" | "exact"
    prefix_len:  int = 128
    action_name: str = "ipv6_forward"
    action_params: Dict[str, str] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
#  Low-level helpers (không cần P4Runtime proto nếu dùng Thrift)
# ══════════════════════════════════════════════════════════════

def _run(cmd: str) -> Tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def _k8s_pod_ready(deploy_name: str, namespace: str = "core-router",
                   timeout: int = 120) -> bool:
    """
    Poll K8s đến khi Deployment báo Ready (Readiness probe pass).
    Đây là điều kiện tiên quyết của QUY TẮC THÉP SỐ 3.
    """
    log.info(f"[MBB] Waiting for K8s Ready: {deploy_name} ...")
    deadline = time.time() + timeout
    # Thử microk8s kubectl trước, sau đó fallback kubectl
    cmd = (
        f"microk8s kubectl get deploy {deploy_name} -n {namespace} "
        f"-o jsonpath='{{.status.readyReplicas}}' 2>/dev/null || "
        f"kubectl get deploy {deploy_name} -n {namespace} "
        f"-o jsonpath='{{.status.readyReplicas}}' 2>/dev/null"
    )
    while time.time() < deadline:
        rc, out = _run(cmd)
        if rc == 0 and out.strip().isdigit() and int(out.strip()) >= 1:
            log.info(f"[MBB] \u2705 {deploy_name} Ready")
            return True
        time.sleep(2)
    log.error(f"[MBB] ❌ Timeout: {deploy_name} not Ready after {timeout}s")
    return False


def _ipv6_to_bytes(addr: str) -> bytes:
    """Chuyển IPv6 string sang 16 bytes (network order)."""
    return socket.inet_pton(socket.AF_INET6, addr)


def _mac_to_bytes(mac: str) -> bytes:
    """Chuyển MAC string sang 6 bytes."""
    return bytes(int(x, 16) for x in mac.split(":"))


# ══════════════════════════════════════════════════════════════
#  ThriftController — fallback khi không có P4Runtime proto
#  Dùng simple_switch_CLI qua Thrift port
# ══════════════════════════════════════════════════════════════

class ThriftController:
    """
    Điều khiển BMv2 qua simple_switch_CLI (Thrift).
    Fallback mode: không cần compile P4Runtime proto.

    simple_switch_CLI --thrift-port 9091 <<EOF
    table_add routing_v6 ipv6_forward fc00::1/128 => 00:00:00:00:00:02 00:00:00:00:00:01 1
    EOF
    """

    def __init__(self, thrift_port: int, switch_name: str = ""):
        self.thrift_port   = thrift_port
        self.switch_name   = switch_name
        # Tên container Docker (phải match với p4_switch.py → bmv2-{name})
        self._container    = f"bmv2-{switch_name}" if switch_name else ""

    def _cli(self, commands: List[str]) -> Tuple[int, str]:
        """
        Gửi lệnh vào simple_switch_CLI bên TRONG Docker container.
        CLI chỉ có trong p4lang/p4app image, không cài trên host.
        """
        cmd_str = "\n".join(commands)
        if self._container:
            # Chạy CLI trong container qua docker exec
            full_cmd = (
                f"echo '{cmd_str}' | "
                f"docker exec -i {self._container} "
                f"simple_switch_CLI --thrift-port {self.thrift_port} 2>&1"
            )
        else:
            # Fallback: CLI trực tiếp trên host (nếu cài BMv2 trực tiếp)
            full_cmd = (
                f"echo '{cmd_str}' | "
                f"simple_switch_CLI --thrift-port {self.thrift_port} 2>&1"
            )
        return _run(full_cmd)

    def add_ipv6_route(
        self, prefix: str, prefix_len: int,
        dst_mac: str, src_mac: str, out_port: int
    ) -> bool:
        """
        Thêm entry vào bảng routing_v6 (LPM).

        Args:
            prefix:     IPv6 prefix (e.g. "fc00::1")
            prefix_len: prefix length (e.g. 128)
            dst_mac:    MAC của next-hop
            src_mac:    MAC của cổng ra
            out_port:   cổng ra của switch (0-indexed)
        """
        cmd = (
            f"table_add routing_v6 ipv6_forward "
            f"{prefix}/{prefix_len} => {dst_mac} {src_mac} {out_port}"
        )
        rc, out = self._cli([cmd])
        if rc == 0 and "error" not in out.lower():
            log.info(f"[{self.switch_name}] route +{prefix}/{prefix_len} → port{out_port}")
            return True
        log.error(f"[{self.switch_name}] table_add failed: {out}")
        return False

    def add_srv6_local_sid(self, sid: str, action: str = "srv6_advance_segment") -> bool:
        """
        Thêm entry vào bảng srv6_local_sid (exact match trên SID).

        Args:
            sid:    SID IPv6 address (e.g. "fc00:1::100")
            action: "srv6_advance_segment" | "drop"
        """
        cmd = f"table_add srv6_local_sid {action} {sid} =>"
        rc, out = self._cli([cmd])
        if rc == 0 and "error" not in out.lower():
            log.info(f"[{self.switch_name}] SID +{sid}")
            return True
        log.error(f"[{self.switch_name}] SID add failed: {out}")
        return False

    def del_ipv6_route(self, prefix: str, prefix_len: int) -> bool:
        """Xoá entry khỏi routing_v6 (dùng khi steer path mới)."""
        cmd = f"table_delete_match routing_v6 {prefix}/{prefix_len}"
        rc, out = self._cli([cmd])
        return rc == 0

    def clear_table(self, table_name: str) -> bool:
        """Xoá toàn bộ entry trong một table."""
        rc, out = self._cli([f"table_clear {table_name}"])
        return rc == 0

    def read_counter(self, counter_name: str, index: int = 0) -> int:
        """
        Đọc giá trị bộ đếm (counter) từ switch.
        Lệnh CLI: counter_read <counter_name> <index>
        """
        cmd = f"counter_read {counter_name} {index}"
        rc, out = self._cli([cmd])
        if rc == 0:
            # Output format: counter_name[index]= packets: X, bytes: Y
            # Ta chỉ cần lấy phần packets
            import re
            match = re.search(r"packets: (\d+)", out)
            if match:
                return int(match.group(1))
        return 0

    def is_reachable(self) -> bool:
        """Kiểm tra Thrift port có mở không."""
        rc, _ = self._cli(["show_tables"])
        return rc == 0


# ══════════════════════════════════════════════════════════════
#  SDNController — Main controller
# ══════════════════════════════════════════════════════════════

class SDNController:
    """
    SDN Controller cho 3S-COM Phase 4.

    Chức năng:
      1. Kết nối đến tất cả P4RuntimeSwitch qua Thrift/gRPC
      2. Populate bảng routing_v6 và srv6_local_sid ban đầu
      3. Thực hiện Make-Before-Break Steer với confirm_steer_done
      4. Expose REST API (/steer, /confirm, /health) cho Backend AI

    QUY TẮC THÉP SỐ 3 (enforce ở đây):
      steer() CHỈ được gọi sau khi _k8s_pod_ready() trả về True.
      confirm_steer_done = True chỉ set sau khi gRPC update thành công.
    """

    def __init__(self, switch_thrift_map: Dict[str, int]):
        """
        Args:
            switch_thrift_map: {switch_name: thrift_port}
              e.g. {"s1": 9091, "s2": 9092, "s3": 9093}
        """
        self.controllers: Dict[str, ThriftController] = {
            name: ThriftController(port, name)
            for name, port in switch_thrift_map.items()
        }
        self._steer_lock   = threading.Lock()
        self._steer_state  = SteerState.IDLE
        self._steer_result: Optional[bool] = None
        # confirm_steer_done: flag Backend AI và Tekton đọc
        self.confirm_steer_done: bool = False

    # ──────────────────────────────────────────────────────────
    #  Bootstrap: populate initial routing tables
    # ──────────────────────────────────────────────────────────

    def bootstrap(self, routing_plan: List[Dict]) -> bool:
        """
        Populate bảng định tuyến ban đầu vào tất cả switches.

        Args:
            routing_plan: list of rule dicts:
              {
                "switch": "s1",
                "type":   "ipv6_route" | "srv6_sid",
                # nếu ipv6_route:
                "prefix":     "fc00:1::/64",
                "prefix_len": 64,
                "dst_mac":    "00:00:00:00:00:02",
                "src_mac":    "00:00:00:00:00:01",
                "out_port":   1,
                # nếu srv6_sid:
                "sid":        "fc00:1::100",
              }
        """
        log.info("[Controller] Bootstrap: populating forwarding tables...")
        ok = True
        for rule in routing_plan:
            sw_name = rule.get("switch")
            ctl     = self.controllers.get(sw_name)
            if not ctl:
                log.warning(f"  Unknown switch: {sw_name}, skip")
                continue

            if rule["type"] == "ipv6_route":
                success = ctl.add_ipv6_route(
                    prefix     = rule["prefix"],
                    prefix_len = rule["prefix_len"],
                    dst_mac    = rule["dst_mac"],
                    src_mac    = rule["src_mac"],
                    out_port   = rule["out_port"],
                )
            elif rule["type"] == "srv6_sid":
                success = ctl.add_srv6_local_sid(rule["sid"])
            else:
                log.warning(f"  Unknown rule type: {rule['type']}")
                success = False

            if not success:
                ok = False

        if ok:
            log.info("[Controller] Bootstrap complete ✅")
        else:
            log.error("[Controller] Bootstrap had errors ❌")
        return ok

    # ──────────────────────────────────────────────────────────
    #  Make-Before-Break Steer (QUY TẮC THÉP SỐ 3)
    # ──────────────────────────────────────────────────────────

    def steer(
        self,
        new_deploy:    str,
        new_rules:     List[Dict],
        old_rules:     List[Dict],
        namespace:     str = "core-router",
        ready_timeout: int = 120,
    ) -> bool:
        """
        Thực hiện Make-Before-Break Steer.

        LUỒNG BẮT BUỘC:
          1. Kiểm tra K8s: new_deploy phải Ready trước khi steer
          2. Gửi gRPC update new_rules xuống switch(es)
          3. Set confirm_steer_done = True
          4. Gọi _notify_break() → Tekton có thể BREAK VNF cũ

        KHÔNG được gọi bước 2 khi new_deploy chưa Ready.
        KHÔNG được set confirm_steer_done trước khi gRPC thành công.

        Returns:
            True  — steer thành công, confirm_steer_done = True
            False — steer thất bại, confirm_steer_done giữ False
        """
        with self._steer_lock:
            self.confirm_steer_done = False
            self._steer_state       = SteerState.WAITING_READY

        log.info(f"[MBB-Steer] START: new_deploy={new_deploy}")

        # ── BƯỚC 1: Chờ K8s Ready (điều kiện tiên quyết) ──────
        if not _k8s_pod_ready(new_deploy, namespace, ready_timeout):
            log.error("[MBB-Steer] ABORT: VNF not Ready → no steer")
            with self._steer_lock:
                self._steer_state = SteerState.FAILED
            return False

        # ── BƯỚC 2: Gửi new_rules xuống switch ────────────────
        with self._steer_lock:
            self._steer_state = SteerState.STEERING

        log.info("[MBB-Steer] VNF Ready ✅ → Installing new forwarding rules...")
        ok = self.bootstrap(new_rules)

        if not ok:
            log.error("[MBB-Steer] ABORT: Failed to install new rules")
            with self._steer_lock:
                self._steer_state = SteerState.FAILED
            return False

        # Xoá rule cũ (optional cleanup trên switch — VNF cũ sẽ bị Tekton BREAK)
        for rule in old_rules:
            sw_name = rule.get("switch")
            ctl     = self.controllers.get(sw_name)
            if ctl and rule["type"] == "ipv6_route":
                ctl.del_ipv6_route(rule["prefix"], rule["prefix_len"])

        # ── BƯỚC 3: Set confirm_steer_done = True ─────────────
        with self._steer_lock:
            self.confirm_steer_done = True
            self._steer_state       = SteerState.DONE

        log.info("[MBB-Steer] ✅ confirm_steer_done = True")
        log.info("[MBB-Steer] Tekton can now BREAK old VNF")
        return True

    def get_steer_status(self) -> Dict:
        """Trả về dict status cho Backend AI hoặc REST poll."""
        with self._steer_lock:
            return {
                "steer_state":         self._steer_state.value,
                "confirm_steer_done":  self.confirm_steer_done,
            }

    # ──────────────────────────────────────────────────────────
    #  Health check
    # ──────────────────────────────────────────────────────────

    def health(self) -> Dict:
        """Trả về trạng thái kết nối từng switch."""
        result = {}
        for name, ctl in self.controllers.items():
            result[name] = {
                "thrift_port": ctl.thrift_port,
                "reachable":   ctl.is_reachable(),
            }
        return result

    def get_msd_drops(self) -> Dict[str, int]:
        """Đọc msd_violation_counter từ tất cả các switch."""
        return {
            name: ctl.read_counter("msd_violation_counter", 0)
            for name, ctl in self.controllers.items()
        }


# ══════════════════════════════════════════════════════════════
#  REST API (Flask mini-server cho Backend AI gọi)
# ══════════════════════════════════════════════════════════════

def start_rest_api(controller: SDNController, port: int = 8765):
    """
    Khởi REST API nhỏ để Backend AI / Tekton giao tiếp với Controller.

    Endpoints:
      GET  /health              → switch connectivity status
      POST /bootstrap           → body: {rules: [...]}
      POST /steer               → body: {new_deploy, new_rules, old_rules}
      GET  /steer/status        → {steer_state, confirm_steer_done}
    """
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json as _json

        ctrl = controller  # closure

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                log.debug(fmt % args)

            def _respond(self, code: int, body: dict):
                payload = _json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                return _json.loads(self.rfile.read(length)) if length else {}

            def do_GET(self):
                if self.path == "/health":
                    self._respond(200, ctrl.health())
                elif self.path == "/steer/status":
                    self._respond(200, ctrl.get_steer_status())
                elif self.path == "/stats/msd_drops":
                    self._respond(200, ctrl.get_msd_drops())
                else:
                    self._respond(404, {"error": "not found"})

            def do_POST(self):
                body = self._body()
                if self.path == "/bootstrap":
                    ok = ctrl.bootstrap(body.get("rules", []))
                    self._respond(200 if ok else 500,
                                  {"ok": ok})
                elif self.path == "/steer":
                    # Chạy async để không block HTTP response
                    def _run_steer():
                        ctrl.steer(
                            new_deploy = body["new_deploy"],
                            new_rules  = body["new_rules"],
                            old_rules  = body.get("old_rules", []),
                            namespace  = body.get("namespace", "core-router"),
                        )
                    threading.Thread(target=_run_steer, daemon=True).start()
                    self._respond(202, {"message": "steer initiated",
                                        "poll": "/steer/status"})
                else:
                    self._respond(404, {"error": "not found"})

        server = HTTPServer(("0.0.0.0", port), Handler)
        log.info(f"[REST] SDN Controller API listening on :{port}")
        server.serve_forever()

    except Exception as e:
        log.error(f"[REST] Failed to start API: {e}")


# ══════════════════════════════════════════════════════════════
#  CLI entry point
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="3S-COM SDN Controller — Phase 4"
    )
    parser.add_argument("--s1-thrift", type=int, default=9091)
    parser.add_argument("--s2-thrift", type=int, default=9092)
    parser.add_argument("--s3-thrift", type=int, default=9093)
    parser.add_argument("--api-port",  type=int, default=8765)
    parser.add_argument("--bootstrap-file", type=str, default="",
                        help="Path to JSON file chứa initial routing rules")
    args = parser.parse_args()

    ctrl = SDNController({
        "s1": args.s1_thrift,
        "s2": args.s2_thrift,
        "s3": args.s3_thrift,
    })

    # Bootstrap nếu có file
    if args.bootstrap_file:
        with open(args.bootstrap_file) as f:
            plan = json.load(f)
        ctrl.bootstrap(plan.get("rules", []))

    # Khởi REST API (blocking)
    start_rest_api(ctrl, args.api_port)
