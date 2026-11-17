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
import threading
import logging
import ipaddress
import re
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
    """Một entry trong routing_v6, srv6_local_sid hoặc srv6_end_dx4_table."""
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
    import subprocess
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()



def _ipv6_to_bytes(addr: str) -> bytes:
    """Chuyển IPv6 string sang 16 bytes (network order)."""
    return socket.inet_pton(socket.AF_INET6, addr)


def _mac_to_bytes(mac: str) -> bytes:
    """Chuyển MAC string sang 6 bytes."""
    return bytes(int(x, 16) for x in mac.split(":"))


def _canonical_ipv6(value: str) -> str:
    """Normalize IPv6 text or the compact hexadecimal form printed by BMv2."""
    value = value.strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", value):
        value = str(ipaddress.IPv6Address(bytes.fromhex(value)))
    return str(ipaddress.IPv6Address(value))


def _canonical_param(value, from_cli=False):
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    value = str(value).strip().lower()
    if re.fullmatch(r"[0-9a-f]{12}", value):
        return value
    if re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", value):
        return value.replace(":", "")
    if from_cli and re.fullmatch(r"[0-9a-f]+", value):
        return str(int(value, 16))
    return value


def parse_table_dump(output: str) -> List[Dict]:
    """Parse BMv2 simple_switch_CLI table_dump output; ignore default entries."""
    if "TABLE ENTRIES" not in output:
        raise ValueError("unrecognized table dump: missing TABLE ENTRIES")
    blocks = re.findall(
        r"Dumping entry\s+(0x[0-9a-fA-F]+)(.*?)(?=\n\s*(?:={3,}|Dumping entry|Dumping default entry)|\Z)",
        output, re.S,
    )
    if not blocks and re.search(r"Dumping entry\s+0x", output):
        raise ValueError("unrecognized table dump entry block")
    entries = []
    for index, body in blocks:
        match = re.search(
            r"\*\s*([\w.]+)\s*:\s*(EXACT|LPM)\s+([^\s]+)", body, re.I
        )
        action = re.search(r"Action entry:\s*[\w.]+\.([\w]+)\s*-\s*(.*)", body)
        if not match or not action:
            raise ValueError("unrecognized table dump entry block")
        match_value = match.group(3)
        prefix_len = None
        if match.group(2).lower() == "lpm":
            if "/" not in match_value:
                raise ValueError("unrecognized LPM match in table dump")
            addr, length = match_value.rsplit("/", 1)
            match_value = f"{_canonical_ipv6(addr)}/{int(length)}"
            prefix_len = int(length)
        elif re.fullmatch(r"[0-9a-fA-F]{32}", match_value):
            match_value = _canonical_ipv6(match_value)
        params_text = action.group(2).strip()
        params = [] if not params_text else [
            _canonical_param(p, from_cli=True) for p in params_text.split(",")
        ]
        entries.append({
            "index": index,
            "match_field": match.group(1),
            "match_type": match.group(2).lower(),
            "match_value": match_value,
            "prefix_len": prefix_len,
            "action_name": action.group(1),
            "action_params": params,
        })
    return entries


def table_entry_matches(entry: Dict, match_value: str, match_type: str,
                        action_name: str, action_params: List) -> bool:
    try:
        requested_prefix_len = None
        if "/" in match_value:
            requested_addr, requested_prefix_len = match_value.rsplit("/", 1)
            expected = f"{_canonical_ipv6(requested_addr)}/{int(requested_prefix_len)}"
        else:
            expected = _canonical_ipv6(match_value)
        if match_type.lower() == "lpm":
            if requested_prefix_len is None:
                expected = f"{expected}/{entry.get('prefix_len') or 128}"
        params = []
        for expected_param, observed_param in zip(action_params, entry["action_params"]):
            expected_canonical = _canonical_param(expected_param)
            if (isinstance(expected_param, str)
                    and (re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", expected_param.lower())
                         or re.fullmatch(r"[0-9a-f]{12}", expected_param.lower()))):
                observed_hex = str(observed_param).lower().replace(":", "")
                if not re.fullmatch(r"[0-9a-f]{1,12}", observed_hex):
                    return False
                observed_canonical = observed_hex.zfill(12)
            else:
                observed_canonical = _canonical_param(observed_param)
            params.append((expected_canonical, observed_canonical))
        return (entry["match_type"] == match_type.lower()
                and entry["match_value"] == expected
                and entry["action_name"] == action_name
                and len(entry["action_params"]) == len(action_params)
                and all(expected_value == observed_value
                        for expected_value, observed_value in params))
    except (KeyError, ValueError, TypeError):
        return False


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
        import subprocess
        cli = ["simple_switch_CLI", "--thrift-port", str(self.thrift_port)]
        cmd = (["docker", "exec", "-i", self._container] + cli
               if self._container else cli)
        try:
            result = subprocess.run(cmd, input="\n".join(commands) + "\n",
                                    capture_output=True, text=True, timeout=15)
            return result.returncode, (result.stdout + result.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 127, str(exc)

    def read_table_entries(self, table_name: str) -> List[Dict]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError("invalid table name")
        rc, output = self._cli([f"table_dump {table_name}"])
        if rc != 0:
            raise RuntimeError(f"table_dump failed for {table_name}: {output}")
        return parse_table_dump(output)

    def verify_table_entry(self, table_name: str, match_value: str,
                           match_type: str, action_name: str,
                           action_params: List) -> bool:
        try:
            entries = self.read_table_entries(table_name)
        except (RuntimeError, ValueError):
            log.exception("[%s] table readback failed: %s", self.switch_name, table_name)
            return False
        matches = [e for e in entries if table_entry_matches(
            e, match_value, match_type, action_name, action_params)]
        return len(matches) == 1

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
        params = [dst_mac, src_mac, out_port]
        if self.verify_table_entry("routing_v6", f"{prefix}/{prefix_len}",
                                   "lpm", "ipv6_forward", params):
            log.info(f"[{self.switch_name}] route +{prefix}/{prefix_len} → port{out_port}")
            return True
        log.error(f"[{self.switch_name}] route readback mismatch (CLI rc=%s): %s", rc, out)
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
        if self.verify_table_entry("srv6_local_sid", sid, "exact", action, []):
            log.info(f"[{self.switch_name}] SID +{sid}")
            return True
        log.error(f"[{self.switch_name}] SID readback mismatch (CLI rc=%s): %s", rc, out)
        return False

    def add_srv6_end_dx4(self, sid: str, dst_mac: str, src_mac: str,
                         out_port: int) -> bool:
        cmd = (f"table_add srv6_end_dx4_table srv6_end_dx4 {sid} => "
               f"{dst_mac} {src_mac} {out_port}")
        rc, out = self._cli([cmd])
        if self.verify_table_entry("srv6_end_dx4_table", sid, "exact",
                                   "srv6_end_dx4", [dst_mac, src_mac, out_port]):
            return True
        log.error("[%s] End.DX4 readback mismatch (CLI rc=%s): %s",
                  self.switch_name, rc, out)
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

    def read_counter(self, counter_name: str, index: int = 0) -> Optional[int]:
        """
        Đọc giá trị bộ đếm (counter) từ switch.
        Lệnh CLI: counter_read <counter_name> <index>
        """
        cmd = f"counter_read {counter_name} {index}"
        rc, out = self._cli([cmd])
        if rc == 0 and "error" not in out.lower():
            # Output format: counter_name[index]= packets: X, bytes: Y
            # Ta chỉ cần lấy phần packets
            import re
            match = re.search(r"\bpackets\s*[:=]\s*(\d+)", out)
            if match:
                return int(match.group(1))
        return None

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
        self._steer_execution_lock = threading.Lock()
        self._steer_state  = SteerState.IDLE
        self._steer_result: Optional[bool] = None
        # confirm_steer_done: flag Backend AI và Tekton đọc
        self.confirm_steer_done: bool = False
        self._steer_deploy: Optional[str] = None
        self._steer_operation_id: Optional[str] = None

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
                "type":   "ipv6_route" | "srv6_sid" | "srv6_end_dx4",
                # nếu ipv6_route:
                "prefix":     "fc00:1::/64",
                "prefix_len": 64,
                "dst_mac":    "00:00:00:00:00:02",
                "src_mac":    "00:00:00:00:00:01",
                "out_port":   1,
                # nếu srv6_sid:
                "sid":        "fc00:1::100",
                # nếu srv6_end_dx4: sid, dst_mac, src_mac, out_port
              }
        """
        log.info("[Controller] Bootstrap: populating forwarding tables...")
        ok = True
        for rule in routing_plan:
            sw_name = rule.get("switch")
            ctl     = self.controllers.get(sw_name)
            if not ctl:
                log.error(f"  Unknown switch: {sw_name}; refusing confirmation")
                ok = False
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
            elif rule["type"] == "srv6_end_dx4":
                success = ctl.add_srv6_end_dx4(
                    sid=rule["sid"], dst_mac=rule["dst_mac"],
                    src_mac=rule["src_mac"], out_port=rule["out_port"],
                )
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

    def steer(self, new_deploy: str, new_rules: List[Dict],
              old_rules: List[Dict], namespace: str = "core-router",
              operation_id: Optional[str] = None) -> bool:
        # Keep status readable during I/O, but serialize complete rule updates.
        with self._steer_execution_lock:
            try:
                return self._steer_once(new_deploy, new_rules, old_rules,
                                        namespace, operation_id)
            except Exception:
                log.exception("Steering failed for %s", new_deploy)
                with self._steer_lock:
                    self.confirm_steer_done = False
                    self._steer_state = SteerState.FAILED
                return False

    def _steer_once(
        self,
        new_deploy:    str,
        new_rules:     List[Dict],
        old_rules:     List[Dict],
        namespace:     str = "core-router",
        operation_id: Optional[str] = None,
    ) -> bool:
        """
        Thực hiện Make-Before-Break Steer — CHỈ XỬ LÝ SWITCH PLANE.

        ⚠️  KIẾN TRÚC: Hàm này KHÔNG tự kiểm tra trạng thái K8s Pod.
        Caller (FastAPI Backend) BẮT BUỘC phải:
          1. Poll K8s bằng kubernetes-python-client cho đến khi new_deploy Ready.
          2. Lấy IP/endpoint của Pod mới từ K8s API.
          3. Chỉ sau đó gọi POST /steer với payload new_rules đã tính sẵn.
        Controller nhận new_rules và nạp thẳng vào switch — Separation of Concerns.

        LUỒNG TRONG HÀM NÀY:
          1. Gửi gRPC/Thrift new_rules xuống switch(es).
          2. Xoá old_rules trên switch.
          3. Set confirm_steer_done = True.

        Returns:
            True  — steer thành công, confirm_steer_done = True
            False — steer thất bại, confirm_steer_done giữ False
        """
        with self._steer_lock:
            self.confirm_steer_done = False
            self._steer_state       = SteerState.STEERING
            self._steer_deploy = new_deploy
            self._steer_operation_id = operation_id

        log.info(f"[MBB-Steer] START: Installing rules for {new_deploy}")

        ok = bool(new_rules) and self.bootstrap(new_rules)

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
                "new_deploy": self._steer_deploy,
                "operation_id": self._steer_operation_id,
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

    def get_msd_drops(self) -> Dict[str, Optional[int]]:
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

            def handle(self):
                try:
                    super().handle()
                except BrokenPipeError:
                    pass  # Im lặng khi client (như curl) đóng kết nối sớm

            def _respond(self, code: int, body: dict):
                try:
                    payload = _json.dumps(body).encode()
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except BrokenPipeError:
                    pass

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
                            operation_id = body.get("operation_id"),
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
        description="3S-COM SDN Controller"
    )
    parser.add_argument("--nodes", type=int, default=10, help="Số lượng switches để điều khiển (mặc định: 10 cho mạng Vietnam)")
    parser.add_argument("--api-port",  type=int, default=8765)
    parser.add_argument("--bootstrap-file", type=str, default="",
                        help="Path to JSON file chứa initial routing rules")
    args = parser.parse_args()

    # Tự động mapping s1 -> 19091, s2 -> 19092 ...
    thrift_map = {f"s{i}": 19090 + i for i in range(1, args.nodes + 1)}
    
    ctrl = SDNController(thrift_map)

    # Nếu chạy độc lập mà không có bootstrap từ mininet, tự nạp SID ban đầu
    if not args.bootstrap_file:
        log.info("[Controller] Auto-bootstrapping default SRv6 SIDs for 10-node topology...")
        initial_routing = [
            {"switch": f"s{i}", "type": "srv6_sid", "sid": f"fc00:{i}::1"}
            for i in range(1, args.nodes + 1)
        ]
        ctrl.bootstrap(initial_routing)
    else:
        with open(args.bootstrap_file) as f:
            plan = json.load(f)
        ctrl.bootstrap(plan.get("rules", []))

    # Khởi REST API (blocking)
    start_rest_api(ctrl, args.api_port)
