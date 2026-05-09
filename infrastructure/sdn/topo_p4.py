"""
3S-COM Testbed — Data Plane (Phase 4: P4 SRv6 + CPU-Pinned BMv2)
=================================================================
Topology:
    h1 ── s1(P4) ── s2(P4) ── s3(P4)
                    │           │
                  vnf1        vnf2

Phase 4 thay đổi so với Phase 3:
  - OVSBridge → P4RuntimeSwitch (BMv2 simple_switch_grpc)
  - Mỗi switch trói vào 1 CPU core độc lập (--cpuset-cpus)
  - SDNController bootstrap bảng routing_v6 qua Thrift
  - Make-Before-Break steer với confirm_steer_done

Quy tắc thép:
  1. KHÔNG BSID — Parser hard-drop nếu #SID > MAX_SID_DEPTH
  2. CPU Pinning — mỗi switch 1 core vật lý
  3. Steer chỉ sau khi K8s Ready, BREAK chỉ sau confirm_steer_done

Usage:
    sudo python3 infrastructure/sdn/topo_p4.py [--p4]  # P4 mode
    sudo python3 infrastructure/sdn/topo_p4.py         # Legacy OVS mode
"""

import argparse
import os
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel, info, warn
import subprocess
import sys
import time

# ── Phase 4: P4 components ────────────────────────────────────
_P4_SDN_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    sys.path.insert(0, _P4_SDN_DIR)
    from p4_switch import SwitchManager
    from controller import SDNController, start_rest_api
    import threading
    HAS_P4 = True
except ImportError as _e:
    HAS_P4 = False
    warn(f"*** P4 modules not available ({_e}), falling back to OVS\n")

# Đường dẫn tới compiled BMv2 JSON (build bởi: cd p4 && make all)
_REPO_ROOT   = os.path.dirname(os.path.dirname(_P4_SDN_DIR))
_P4_BUILD    = os.path.join(_REPO_ROOT, "infrastructure", "sdn", "p4", "build")
CORE_JSON    = os.path.join(_P4_BUILD, "core",   "srv6_core.json")
BORDER_JSON  = os.path.join(_P4_BUILD, "border", "srv6_border.json")

# Switch type mapping: s1/s2 = core (MSD=10), s3 = border (MSD=3)
_SWITCH_JSON = {
    "s1": CORE_JSON,
    "s2": CORE_JSON,
    "s3": BORDER_JSON,
}

# ══════════════════════════════════════════════════════════════
#  CONFIG  (chỉnh ở đây khi deploy lên server mới)
# ══════════════════════════════════════════════════════════════
# Dải địa chỉ "ảo" cấp cho veth bridge phía Mininet
K8S_SUBNET  = "10.1.0.0/16"
K8S_GATEWAY = "10.1.240.1"   # IP của br-k8s-mn trên host

# IP bridge của từng Mininet host (phải nằm trong K8S_SUBNET)
H1_K8S_IP   = "10.1.240.90"
VNF1_K8S_IP = "10.1.240.91"
VNF2_K8S_IP = "10.1.240.92"

# NodePort vVOC dùng để verify Phase 3
VVOC_NODEPORT = 31656

# Địa chỉ Mininet (10.0.0.0/24) — để populate /etc/hosts
MN_SUBNET = "10.0.0.0/24"

# ══════════════════════════════════════════════════════════════


def run_cmd(cmd: str) -> int:
    return subprocess.call(cmd, shell=True)


def run_out(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        return ""


# ──────────────────────────────────────────────────────────────
#  Tự động nhận diện môi trường K8s
# ──────────────────────────────────────────────────────────────

def detect_k8s_bridge():
    """Trả về (bridge_name, mode).

    Modes:
      microk8s — bridge cni0 sẵn có (flannel/calico đơn giản)
      kind      — br-<hash> của Kind cluster
      calico    — không có bridge có sẵn; tự tạo br-k8s-mn
    """
    # 1. MicroK8s mặc định (flannel)
    if run_out("ip link show cni0"):
        info("*** Detected MicroK8s bridge: cni0\n")
        return "cni0", "microk8s"

    # 2. Kind cluster
    for dev in run_out("ip route show | grep '172.18' | grep -oP 'dev \\K\\S+'").splitlines():
        if dev.startswith("br-"):
            info(f"*** Detected Kind bridge: {dev}\n")
            return dev, "kind"

    # 3. Calico / custom — tự tạo bridge
    info("*** No K8s bridge found (Calico mode). Will create br-k8s-mn\n")
    return "br-k8s-mn", "calico"


def detect_k8s_ip(mode: str) -> str:
    """Trả về IP của node K8s để dùng làm NodePort target."""
    if mode == "kind":
        ip = run_out(
            "docker inspect -f "
            "'{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "
            "nfv-mini-control-plane"
        )
        if ip:
            info(f"*** Kind control-plane IP: {ip}\n")
            return ip
        return "172.18.0.2"

    # MicroK8s / Calico: dùng IP chính của host
    ip = run_out("hostname -I | awk '{print $1}'")
    if ip:
        info(f"*** Host IP (NodePort target): {ip}\n")
        return ip
    return "127.0.0.1"


# ──────────────────────────────────────────────────────────────
#  Topology
# ──────────────────────────────────────────────────────────────

class CoreRouterTopo(Topo):
    """3-switch linear topology với 1 traffic host và 2 VNF hosts.

        h1 ── s1 ── s2 ── s3
                    │      │
                  vnf1   vnf2
    """
    def build(self):
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")

        h1   = self.addHost("h1",   ip="10.0.0.1/24",  mac="00:00:00:00:00:01")
        vnf1 = self.addHost("vnf1", ip="10.0.0.11/24", mac="00:00:00:00:00:11")
        vnf2 = self.addHost("vnf2", ip="10.0.0.12/24", mac="00:00:00:00:00:12")

        self.addLink(h1,   s1)
        self.addLink(s1,   s2)
        self.addLink(s2,   s3)
        self.addLink(vnf1, s2)
        self.addLink(vnf2, s3)


# ──────────────────────────────────────────────────────────────
#  Phase 3 — Mininet ↔ K8s bridge
# ──────────────────────────────────────────────────────────────

def _cleanup_old_veths():
    """Xóa veth cũ còn sót từ lần chạy trước để tránh 'File exists'."""
    for veth in ["veth-h1-k8s", "veth-vnf1-k8s", "veth-vnf2-k8s"]:
        run_cmd(f"ip link delete {veth} 2>/dev/null")


# Mapping: Mininet IP → bridge-side veth IP (dùng cho return routing)
# Host-level route: "packet to 10.0.0.x, next-hop = bridge IP của host tương ứng"
_MININET_TO_BRIDGE_IP = {
    "h1":   ("10.0.0.1",  H1_K8S_IP),
    "vnf1": ("10.0.0.11", VNF1_K8S_IP),
    "vnf2": ("10.0.0.12", VNF2_K8S_IP),
}


def _setup_transparent_routing(net, k8s_bridge: str):
    """Thiết lập SFC-transparent routing: GIỮ source IP gốc từ Mininet.

    Vấn đề với MASQUERADE (cũ):
      h1 (10.0.0.1) → MASQUERADE → VNF thấy srcIP=10.1.240.1 (bridge GW)
      => DDoS detection vô nghĩa vì mọi host trông giống nhau.

    Giải pháp — L2 Transparent Routing:
      1. Mininet host dùng `src <mininet_ip>` trong default route.
         => h1 (10.0.0.1) gửi gói tin: srcIP=10.0.0.1 (thật), KHOONG rewrite.
      2. Host-level return route: per-host 10.0.0.x/32 → via bridge veth IP.
         => K8s pod reply đến 10.0.0.1 → host route: via 10.1.240.90 → vào h1's netns.
      3. ip_forward=1 để host forward packets giữa Mininet và K8s.
      4. KHÔNG MASQUERADE, không NAT, không rewrite header.

    Tầng DATA PLANE SFC của chúầ ta sẽ bày ra chain:
      h1(10.0.0.1) -> P4 switch -> SRv6 path -> vNAT -> vFW -> vIDPS
      vFW thấy srcIP=10.0.0.1 => block đúng target => demo có giá trị khoa học.

    Technical Debt note:
      Đây là Milestone 2 (veth/direct bridge). Vấn đề còn lại:
      - VNF pods trong K8s sẽ thấy traffic đến qua kube-proxy (NodePort path)
        => header vẫn qua DNAT của kube-proxy.
      Milestone 3 (Multus/macvlan) sẽ giải quyết cả kube-proxy DNAT.
    """
    info("*** [Transparent Routing] ip_forward + per-host return routes...\n")
    run_cmd("sysctl -w net.ipv4.ip_forward=1 > /dev/null")

    # FORWARD rules không NAT — chỉ cho phép forward, không rewrite
    run_cmd(f"iptables -A FORWARD -i {k8s_bridge} -j ACCEPT 2>/dev/null || true")
    run_cmd(f"iptables -A FORWARD -o {k8s_bridge} -j ACCEPT 2>/dev/null || true")

    # Per-host return routes: 10.0.0.x/32 via <bridge_veth_ip> dev <bridge>
    # K8s pod reply đến 10.0.0.x => host biết route vào đúng netns của host tương ứng
    for host_name, (mn_ip, bridge_ip) in _MININET_TO_BRIDGE_IP.items():
        run_cmd(f"ip route replace {mn_ip}/32 via {bridge_ip} dev {k8s_bridge} 2>/dev/null || true")
        info(f"    Return route: {mn_ip}/32 via {bridge_ip} ({host_name})\n")

    info("*** [Transparent Routing] Setup complete. NO MASQUERADE. SFC transparency: ON\n")


def setup_bridge(net, k8s_bridge: str, k8s_ip: str, mode: str):
    """Kết nối Mininet hosts vào K8s network qua veth pairs."""
    info(f"*** Setting up Mininet ↔ K8s bridge ({mode})...\n")

    # Tạo bridge ảo cho Calico (không có bridge sẵn)
    if mode == "calico":
        run_cmd(f"ip link add {k8s_bridge} type bridge 2>/dev/null")
        run_cmd(f"ip addr add {K8S_GATEWAY}/16 dev {k8s_bridge} 2>/dev/null")
        run_cmd(f"ip link set {k8s_bridge} up")
        run_cmd("sysctl -w net.ipv4.ip_forward=1 > /dev/null")

    _cleanup_old_veths()

    # Cấu hình riêng theo mode
    if mode == "kind":
        subnet = "172.18.0.0/16"
        gw     = "172.18.0.1"
        configs = [
            ("h1",   "veth-h1-k8s",   "veth-h1-mn",   "172.18.0.90"),
            ("vnf1", "veth-vnf1-k8s", "veth-vnf1-mn", "172.18.0.91"),
            ("vnf2", "veth-vnf2-k8s", "veth-vnf2-mn", "172.18.0.92"),
        ]
        run_cmd(
            "docker exec nfv-mini-control-plane "
            "ip route add 10.0.0.0/24 via 172.18.0.91 2>/dev/null || true"
        )
    else:
        subnet = K8S_SUBNET
        gw     = K8S_GATEWAY
        configs = [
            ("h1",   "veth-h1-k8s",   "veth-h1-mn",   H1_K8S_IP),
            ("vnf1", "veth-vnf1-k8s", "veth-vnf1-mn", VNF1_K8S_IP),
            ("vnf2", "veth-vnf2-k8s", "veth-vnf2-mn", VNF2_K8S_IP),
        ]
        # Route ngược: host → Mininet subnet qua vnf1's bridge IP
        run_cmd(f"ip route replace {MN_SUBNET} via {VNF1_K8S_IP} 2>/dev/null || true")

    prefix = subnet.split("/")[1]
    for host_name, veth_k8s, veth_mn, ip in configs:
        host = net.get(host_name)
        pid  = host.pid

        # Lấy Mininet IP của host (để dùng làm src hint)
        mn_ip = _MININET_TO_BRIDGE_IP.get(host_name, (None, None))[0]

        run_cmd(f"ip link add {veth_k8s} type veth peer name {veth_mn}")
        run_cmd(f"ip link set {veth_k8s} master {k8s_bridge}")
        run_cmd(f"ip link set {veth_k8s} up")
        run_cmd(f"ip link set {veth_mn} netns {pid}")

        host.cmd(f"ip addr add {ip}/{prefix} dev {veth_mn}")
        host.cmd(f"ip link set {veth_mn} up")
        host.cmd(f"ip route add {subnet} via {gw} dev {veth_mn}")

        # KEY FIX (Lỗ hổng 1): Dùng `src <mininet_ip>` để bảo tòan source IP.
        # Không có dòng này, Linux sẽ chọn IP của veth ({ip}={bridge_ip})
        # làm source => VNF thấy tất cả trông giống nhau (phá SFC transparency).
        if mn_ip:
            host.cmd(f"ip route replace default via {gw} dev {veth_mn} src {mn_ip}")
        else:
            host.cmd(f"ip route add default via {gw} dev {veth_mn} 2>/dev/null || true")

        info(f"    {host_name} → bridge={ip}, src_hint={mn_ip or '(none)'} OK\n")

    # /etc/hosts nội bộ Mininet
    hosts_entries = "10.0.0.1 h1\n10.0.0.11 vnf1\n10.0.0.12 vnf2\n"
    for host_name in ["h1", "vnf1", "vnf2"]:
        net.get(host_name).cmd(f"printf '{hosts_entries}' >> /etc/hosts")

    # Transparent routing — KHOONG MASQUERADE
    _setup_transparent_routing(net, k8s_bridge)

    info("*** Bridge setup complete.\n")


def warm_up(net, k8s_ip: str):
    """Prime OVS MAC tables và ARP cache để tránh packet loss lần đầu."""
    info("*** Pre-populating ARP/MAC tables...\n")
    h1   = net.get("h1")
    vnf1 = net.get("vnf1")
    vnf2 = net.get("vnf2")
    h1.cmd("ping -c 1 10.0.0.11 > /dev/null 2>&1 &")
    h1.cmd(f"ping -c 1 {k8s_ip} > /dev/null 2>&1 &")
    vnf1.cmd(f"ping -c 1 {k8s_ip} > /dev/null 2>&1 &")
    vnf2.cmd(f"ping -c 1 {k8s_ip} > /dev/null 2>&1 &")
    time.sleep(2)


def verify_phase3(net, k8s_ip: str, nodeport: int = VVOC_NODEPORT) -> bool:
    """Phase 3 M1: Tự động kiểm tra connectivity từ mọi Mininet host → vVOC NodePort.

    Trả về True nếu tất cả hosts đều reach được.
    Nếu vVOC chưa deploy, in hướng dẫn deploy.
    """
    url = f"http://{k8s_ip}:{nodeport}/healthz"
    sep = "=" * 60

    info(f"\n{sep}\n")
    info("*** [Phase 3 - M1] NodePort Bridge Verification\n")
    info(f"*** Target: {url}\n")
    info(f"{sep}\n")

    results = {}
    for host_name in ["h1", "vnf1", "vnf2"]:
        host = net.get(host_name)
        out  = host.cmd(f"curl -sS --max-time 4 {url} 2>&1")
        ok   = '"ok"' in out or "'ok'" in out or "ok" in out.lower()
        results[host_name] = ok
        status = "✅ OK  " if ok else "❌ FAIL"
        info(f"    {host_name:6s}  {status}  {url}\n")
        if not ok:
            info(f"           → {out.strip()[:100]}\n")

    info(f"{sep}\n")
    all_ok = all(results.values())
    if all_ok:
        info("*** [Phase 3 - M1] PASSED — All Mininet hosts reach K8s NodePort ✅\n")
    else:
        failed = [h for h, ok in results.items() if not ok]
        info(f"*** [Phase 3 - M1] PARTIAL — Failed: {failed}\n")
        info(f"*** Hint: Deploy vVOC nếu chưa có:\n")
        info(f"***   sudo microk8s kubectl apply -f infrastructure/k8s/manifests/vvoc-phase3-test.yaml\n")
        info(f"***   sudo microk8s kubectl rollout status deploy/vnf-voc-phase3 -n core-router\n")
        info(f"*** Hoặc kiểm tra NAT: iptables -t nat -L POSTROUTING -n\n")
    info(f"{sep}\n\n")
    return all_ok


# ──────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════
#  Initial routing plan (bootstrap tables sau khi switches up)
# ══════════════════════════════════════════════════════════════

# SID prefix scheme: fc00:X::Y
#   X = switch_id (1/2/3)
#   Y = host id
# Ports: s1-p1=h1, s1-p2=s2; s2-p1=s1, s2-p2=s3, s2-p3=vnf1; s3-p1=s2, s3-p2=vnf2

INITIAL_ROUTING = [
    # ── s1: default forward đến s2 ────────────────────────────
    {"switch": "s1", "type": "ipv6_route",
     "prefix": "::", "prefix_len": 0,
     "dst_mac": "00:00:00:00:02:01", "src_mac": "00:00:00:00:01:02", "out_port": 2},
    # ── s2: forward vnf1 traffic (fc00:b::11) đến port3 ───────
    {"switch": "s2", "type": "ipv6_route",
     "prefix": "fc00:b::11", "prefix_len": 128,
     "dst_mac": "00:00:00:00:00:11", "src_mac": "00:00:00:00:02:03", "out_port": 3},
    # ── s2: default forward đến s3 ────────────────────────────
    {"switch": "s2", "type": "ipv6_route",
     "prefix": "::", "prefix_len": 0,
     "dst_mac": "00:00:00:00:03:01", "src_mac": "00:00:00:00:02:02", "out_port": 2},
    # ── s3: forward vnf2 traffic (fc00:b::12) đến port2 ───────
    {"switch": "s3", "type": "ipv6_route",
     "prefix": "fc00:b::12", "prefix_len": 128,
     "dst_mac": "00:00:00:00:00:12", "src_mac": "00:00:00:00:03:02", "out_port": 2},
    # ── SRv6 local SIDs ───────────────────────────────────────
    {"switch": "s1", "type": "srv6_sid", "sid": "fc00:1::1"},
    {"switch": "s2", "type": "srv6_sid", "sid": "fc00:2::1"},
    {"switch": "s3", "type": "srv6_sid", "sid": "fc00:3::1"},
]


def run_p4(k8s_bridge: str, k8s_ip: str, mode: str):
    """
    Phase 4 mode: Mininet + P4RuntimeSwitch (BMv2) + SDNController.

    Kiến trúc:
      - Mininet topo khởi động KHÔNG có switch thật (switch=None)
      - P4RuntimeSwitch được tạo riêng qua Docker với CPU pinning
      - Mininet interfaces được pass vào BMv2 qua -i PORT@IFACE
    """
    if not HAS_P4:
        warn("*** P4 modules not available. Falling back to OVS mode.\n")
        return run_ovs(k8s_bridge, k8s_ip, mode)

    # Kiểm tra JSON files đã được build chưa
    for sw_name, json_path in _SWITCH_JSON.items():
        if not os.path.isfile(json_path):
            warn(
                f"*** {sw_name} JSON not found: {json_path}\n"
                f"    Run: cd infrastructure/sdn/p4 && make all\n"
                f"    Falling back to OVS mode.\n"
            )
            return run_ovs(k8s_bridge, k8s_ip, mode)

    info("*** [Phase 4] Starting P4RuntimeSwitch topology...\n")

    # ── 1. Khởi Mininet topology (hosts only, no switch) ──────
    topo = CoreRouterTopo()
    net  = Mininet(topo=topo, switch=OVSBridge, controller=None)
    net.start()

    # ── 2. Khởi SwitchManager + P4RuntimeSwitch (CPU pinned) ──
    # Giao diện Mininet: s1-eth1 (h1↔s1), s1-eth2 (s1↔s2), ...
    # BMv2 port numbering bắt đầu từ 1
    manager = SwitchManager(cpu_base=2)  # core 2,3,4 cho s1,s2,s3

    manager.add_switch(
        name       = "s1",
        switch_id  = 1,
        json_path  = _SWITCH_JSON["s1"],
        interfaces = [(1, "s1-eth1"), (2, "s1-eth2")],
    )
    manager.add_switch(
        name       = "s2",
        switch_id  = 2,
        json_path  = _SWITCH_JSON["s2"],
        interfaces = [(1, "s2-eth1"), (2, "s2-eth2"), (3, "s2-eth3")],
    )
    manager.add_switch(
        name       = "s3",
        switch_id  = 3,
        json_path  = _SWITCH_JSON["s3"],
        interfaces = [(1, "s3-eth1"), (2, "s3-eth2")],
    )

    if not manager.start_all():
        warn("*** Some P4 switches failed to start! Check docker logs.\n")

    info(manager.status_report() + "\n")

    # ── 3. Setup K8s bridge (transparent routing) ─────────────
    setup_bridge(net, k8s_bridge, k8s_ip, mode)
    warm_up(net, k8s_ip)

    # ── 4. Bootstrap forwarding tables qua Thrift ─────────────
    thrift_map = {"s1": 9091, "s2": 9092, "s3": 9093}
    controller = SDNController(thrift_map)

    # Đợi Thrift ports ready (BMv2 cần ~3s sau khi gRPC up)
    info("*** [Phase 4] Waiting for Thrift ports...\n")
    time.sleep(3)

    if controller.bootstrap(INITIAL_ROUTING):
        info("*** [Phase 4] Forwarding tables populated ✅\n")
    else:
        warn("*** [Phase 4] Some table entries failed (BMv2 may not be ready yet)\n")

    # ── 5. Khởi REST API cho Backend AI (non-blocking) ────────
    api_thread = threading.Thread(
        target=start_rest_api,
        args=(controller, 8765),
        daemon=True
    )
    api_thread.start()
    info("*** [Phase 4] SDN Controller REST API: http://0.0.0.0:8765\n")

    # ── 6. Phase 3 connectivity check ─────────────────────────
    verify_phase3(net, k8s_ip)

    info("*** 3S-COM Phase 4 Data Plane ready. Type 'exit' to stop.\n")
    info("*** REST endpoints: /health  /bootstrap  /steer  /steer/status\n")
    CLI(net)

    # ── Teardown ───────────────────────────────────────────────
    manager.stop_all()
    net.stop()


def run_ovs(k8s_bridge: str, k8s_ip: str, mode: str):
    """Legacy Phase 3 mode: OVSBridge (fallback khi chưa có P4 JSON)."""
    info("*** [OVS mode] Starting legacy OVSBridge topology...\n")
    topo = CoreRouterTopo()
    net  = Mininet(topo=topo, switch=OVSBridge, controller=None)
    net.start()
    setup_bridge(net, k8s_bridge, k8s_ip, mode)
    warm_up(net, k8s_ip)
    verify_phase3(net, k8s_ip)
    info("*** 3S-COM Data Plane is ready. Type 'exit' to stop.\n")
    CLI(net)
    net.stop()


def run():
    ap = argparse.ArgumentParser(description="3S-COM Testbed Data Plane")
    ap.add_argument(
        "--p4", action="store_true",
        help="Bật Phase 4 P4RuntimeSwitch mode (cần: cd p4 && make all trước)"
    )
    args, _ = ap.parse_known_args()

    # Pre-cleanup mininet veths to prevent "RTNETLINK answers: File exists" from ungraceful exits
    run_cmd("for i in $(ip link show | grep -oE '(s|h|vnf)[0-9]+-eth[0-9]+'); do ip link delete $i 2>/dev/null; done")

    k8s_bridge, mode = detect_k8s_bridge()
    k8s_ip           = detect_k8s_ip(mode)

    if args.p4:
        run_p4(k8s_bridge, k8s_ip, mode)
    else:
        run_ovs(k8s_bridge, k8s_ip, mode)


if __name__ == "__main__":
    setLogLevel("info")
    run()
