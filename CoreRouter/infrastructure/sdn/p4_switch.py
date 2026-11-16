"""
3S-COM Testbed — Phase 4: P4RuntimeSwitch (BMv2 + CPU Pinning)
===============================================================

Class P4RuntimeSwitch thay thế OVSBridge trong topo_p4.py.
Mỗi switch là một Docker container chạy simple_switch_grpc,
bị trói vào 1 CPU core vật lý độc lập bằng --cpuset-cpus.

ĐÂY LÀ QUY TẮC THÉP SỐ 2:
  CPU Pinning bắt buộc để đạt Line-rate giả lập phần cứng.
  Nếu không pin CPU, jitter từ K8s sẽ làm nhiễu đường Latency
  trên Wireshark — phá hỏng giá trị thực nghiệm của Luận văn.

Kiến trúc:
  - BMv2 image: p4lang/behavioral-model:latest
  - Switch mode: simple_switch_grpc (hỗ trợ P4Runtime gRPC)
  - Mỗi switch chiếm 1 CPU core riêng (--cpuset-cpus N)
  - gRPC port: 50051 + switch_id (50051, 50052, ...)
  - Thrift port: 19091 + switch_id (19091, 19092, ...) — tránh xung đột với services hệ thống

Usage:
    Xem topo_p4.py — không gọi trực tiếp.
"""

import subprocess
import time
import os
import signal
import socket
import json
from typing import Optional, List, Dict
from mininet.log import info, warn, error


# ══════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════

# Đúng image: p4lang/p4app có đủ simple_switch_grpc, simple_switch_CLI, p4c
BMV2_IMAGE      = "p4lang/p4app:latest"
BMV2_LOG_LEVEL  = "warn"   # trace|debug|info|warn|error

# CPU core assignment (topo_p4.py sẽ pass cpu_core=N)
# Core 0-1: dành cho K8s system pods
# Core 2+:  dành cho BMv2 switches
# Thứ tự mặc định: s1→core2, s2→core3, s3→core4
DEFAULT_CPU_BASE = 2


# ══════════════════════════════════════════════════════════════
#  Helper
# ══════════════════════════════════════════════════════════════

def _run(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
    """Chạy shell command, trả về CompletedProcess."""
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        check=check
    )


def _wait_port(host: str, port: int, timeout: float = 15.0) -> bool:
    """Chờ đến khi TCP port mở (dùng để detect BMv2 gRPC ready)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    return False


# ══════════════════════════════════════════════════════════════
#  P4RuntimeSwitch
# ══════════════════════════════════════════════════════════════

class P4RuntimeSwitch:
    """
    BMv2 simple_switch_grpc chạy trong Docker container với CPU pinning.

    Attributes:
        name        — tên switch (e.g. "s1")
        switch_id   — device-id (1-indexed)
        json_path   — đường dẫn tuyệt đối đến compiled BMv2 JSON
        cpu_core    — CPU core vật lý bị trói vào (--cpuset-cpus)
        grpc_port   — gRPC listen port (50050 + switch_id)
        thrift_port — Thrift listen port (9089 + switch_id)
        interfaces  — list of (port_num, iface_name)
        container_id— Docker container ID (sau khi start)
    """

    def __init__(
        self,
        name: str,
        switch_id: int,
        json_path: str,
        cpu_core: int,
        interfaces: List[tuple],          # [(port_num, iface_name), ...]
        grpc_port: Optional[int] = None,
        thrift_port: Optional[int] = None,
        log_level: str = BMV2_LOG_LEVEL,
    ):
        self.name        = name
        self.switch_id   = switch_id
        self.json_path   = os.path.abspath(json_path)
        self.cpu_core    = cpu_core
        self.interfaces  = interfaces
        self.grpc_port   = grpc_port   or (50050 + switch_id)
        self.thrift_port = thrift_port or (19090 + switch_id)
        self.log_level   = log_level
        self.container_id: Optional[str] = None
        self._container_name = f"bmv2-{name}"

    # ──────────────────────────────────────────────────────────
    #  Start
    # ──────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Khởi động BMv2 container với CPU pinning.

        Docker flags quan trọng:
          --cpuset-cpus {cpu_core}  ← QUY TẮC THÉP: 1 core / switch
          --network host            ← cần để bind vào Mininet interfaces
          --privileged              ← cần để manipulate netns
          --name bmv2-{name}        ← để stop/rm dễ dàng
        """
        # Kill container cũ nếu còn sót
        self._cleanup_existing()

        # Kiểm tra JSON file tồn tại
        if not os.path.isfile(self.json_path):
            error(
                f"[P4Switch:{self.name}] JSON not found: {self.json_path}\n"
                f"  Run: cd infrastructure/sdn/p4 && make all\n"
            )
            return False

        # Build interface flags: -i PORT@IFACE
        iface_flags = " ".join(
            f"-i {port}@{iface}" for port, iface in self.interfaces
        )

        # Xác định thư mục chứa JSON để mount vào container
        json_dir  = os.path.dirname(self.json_path)
        json_file = os.path.basename(self.json_path)

        cmd = (
            f"docker run -d "
            f"--name {self._container_name} "
            # ─── CPU PINNING (Quy tắc thép số 2) ─────────────
            f"--cpuset-cpus {self.cpu_core} "
            # ─── Network & privilege ──────────────────────────
            f"--network host "
            f"--privileged "
            # ─── Volume: mount thư mục chứa compiled JSON ─────
            f"-v {json_dir}:/data:ro "
            f"--entrypoint simple_switch "
            f"{BMV2_IMAGE} "
            # ─── BMv2 command ─────────────────────────────────
            f"--device-id {self.switch_id} "
            f"--thrift-port {self.thrift_port} "
            f"--log-console "
            f"--log-level {self.log_level} "
            f"{iface_flags} "
            f"/data/{json_file}"
        )

        info(
            f"*** [P4Switch:{self.name}] Starting BMv2 "
            f"(cpu={self.cpu_core}, Thrift={self.thrift_port})...\n"
        )
        result = _run(cmd)
        if result.returncode != 0:
            error(f"[P4Switch:{self.name}] docker run failed: {result.stderr.strip()}\n")
            return False

        self.container_id = result.stdout.strip()[:12]
        info(f"    Container: {self.container_id}\n")

        # Wait for Thrift port
        info(f"    Waiting for Thrift port {self.thrift_port}...\n")
        if not _wait_port("127.0.0.1", self.thrift_port, timeout=25.0):
            error(
                f"[P4Switch:{self.name}] Thrift port {self.thrift_port} not open in 25s\n"
                f"  Logs:\n{self.get_logs(8)}\n"
            )
            return False

        info(f"    \u2705 {self.name} ready (Thrift:{self.thrift_port})\n")
        return True

    # ──────────────────────────────────────────────────────────
    #  Stop
    # ──────────────────────────────────────────────────────────

    def stop(self):
        """Dừng và xoá Docker container."""
        info(f"*** [P4Switch:{self.name}] Stopping container...\n")
        _run(f"docker stop {self._container_name} 2>/dev/null")
        _run(f"docker rm   {self._container_name} 2>/dev/null")
        self.container_id = None

    # ──────────────────────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────────────────────

    def _cleanup_existing(self):
        """Xoá container cũ cùng tên và đợi port free."""
        _run(f"docker stop {self._container_name} 2>/dev/null")
        _run(f"docker rm   {self._container_name} 2>/dev/null")
        self._wait_port_free(timeout=4.0)

    def _wait_port_free(self, timeout: float = 5.0) -> bool:
        """Chờ cho đến khi Thrift port KHÔNG còn bị chiếm (ngược với _wait_port)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.thrift_port), timeout=0.3):
                    time.sleep(0.3)  # Port vẫn còn occupied → chờ tiếp
            except (ConnectionRefusedError, OSError):
                return True  # Port đã free
        return False  # Vẫn chưa free sau timeout — tiếp tục và để BMv2 thử

    def is_running(self) -> bool:

        """Kiểm tra container còn alive không."""
        result = _run(
            f"docker inspect -f '{{{{.State.Running}}}}' "
            f"{self._container_name} 2>/dev/null"
        )
        return result.stdout.strip() == "true"

    def get_logs(self, tail: int = 20) -> str:
        """Lấy log cuối từ container (để debug)."""
        result = _run(f"docker logs --tail {tail} {self._container_name} 2>&1")
        return result.stdout + result.stderr

    def __repr__(self) -> str:
        status = "running" if self.is_running() else "stopped"
        return (
            f"P4RuntimeSwitch(name={self.name}, "
            f"id={self.switch_id}, "
            f"cpu={self.cpu_core}, "
            f"grpc={self.grpc_port}, "
            f"status={status})"
        )


# ══════════════════════════════════════════════════════════════
#  SwitchManager — quản lý tập hợp các switch
# ══════════════════════════════════════════════════════════════

class SwitchManager:
    """
    Quản lý vòng đời của tất cả P4RuntimeSwitch trong topology.

    Đảm bảo:
      - Mỗi switch có CPU core độc lập (không share)
      - Cleanup đúng thứ tự khi teardown
      - Interface với Controller qua port registry
    """

    def __init__(self, cpu_base: int = DEFAULT_CPU_BASE):
        self.cpu_base  = cpu_base
        self.switches: Dict[str, P4RuntimeSwitch] = {}
        self._next_cpu = cpu_base

    def add_switch(
        self,
        name: str,
        switch_id: int,
        json_path: str,
        interfaces: List[tuple],
        cpu_core: Optional[int] = None,
    ) -> P4RuntimeSwitch:
        """
        Đăng ký switch mới, tự động cấp CPU core nếu không chỉ định.

        Args:
            cpu_core: None → tự động cấp core tiếp theo (round-robin)
        """
        if cpu_core is None:
            cpu_core = self._next_cpu
            self._next_cpu += 1

        sw = P4RuntimeSwitch(
            name=name,
            switch_id=switch_id,
            json_path=json_path,
            cpu_core=cpu_core,
            interfaces=interfaces,
        )
        self.switches[name] = sw
        return sw

    def start_all(self) -> bool:
        """Khởi động tất cả switch. Trả về False nếu bất kỳ switch nào fail."""
        info("*** [SwitchManager] Starting all P4 switches...\n")
        ok = True
        for name, sw in self.switches.items():
            if not sw.start():
                error(f"[SwitchManager] FAILED to start {name}\n")
                ok = False
        if ok:
            info("*** [SwitchManager] All switches running ✅\n")
        return ok

    def stop_all(self):
        """Dừng tất cả switch theo thứ tự ngược lại (an toàn hơn)."""
        info("*** [SwitchManager] Stopping all P4 switches...\n")
        for sw in reversed(list(self.switches.values())):
            sw.stop()
        info("*** [SwitchManager] All switches stopped.\n")

    def get_grpc_map(self) -> Dict[str, int]:
        """Trả về {switch_name: grpc_port} cho Controller biết cần kết nối đâu."""
        return {name: sw.grpc_port for name, sw in self.switches.items()}

    def status_report(self) -> str:
        """Bảng trạng thái cho CLI / debug."""
        lines = [
            "╔══════════════════════════════════════╗",
            "║  P4 Switch Status                    ║",
            "╠══════════════════════════════════════╣",
        ]
        for name, sw in self.switches.items():
            status = "✅ UP" if sw.is_running() else "❌ DOWN"
            lines.append(
                f"║  {name:5s}  cpu={sw.cpu_core}  "
                f"gRPC={sw.grpc_port}  {status:8s}   ║"
            )
        lines.append("╚══════════════════════════════════════╝")
        return "\n".join(lines)
