"""
3S-COM Testbed — Data Plane (Phase 7: Vietnam 10-node P4 SRv6 + CPU-Pinned BMv2)
================================================================================
Topology:
    Vietnam 10-node backbone using Haversine distances for delays.
    10 P4 switches mapped to 10 VNF pods.

Quy tắc thép:
  1. KHÔNG BSID — Parser hard-drop nếu #SID > MAX_SID_DEPTH
  2. CPU Pinning — Switch Core trói độc quyền 1 core, Switch Edge chia sẻ core.
  3. Link Matrix — TCLink với Haversine delay thực tế.
  4. L2 Transparent Routing bảo toàn Source IP.

Usage:
    sudo python3 infrastructure/sdn/topo_p4.py [--p4]  # P4 mode
    sudo python3 infrastructure/sdn/topo_p4.py         # Legacy OVS mode
"""

import argparse
import os
import sys
import subprocess
import time

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel, info, warn
from mininet.link import TCLink

# ── Phase 4/7: P4 components ────────────────────────────────────
_P4_SDN_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.dirname(os.path.dirname(_P4_SDN_DIR))

# Import topoplogy definition
sys.path.insert(0, _REPO_ROOT)
from src.orchestration.jo_vdpr.topology import TOPOLOGIES, _haversine_km, FIBER_SPEED_KM_PER_MS

try:
    sys.path.insert(0, _P4_SDN_DIR)
    from p4_switch import SwitchManager
    from controller import SDNController, start_rest_api
    import threading
    HAS_P4 = True
except ImportError as _e:
    HAS_P4 = False
    warn(f"*** P4 modules not available ({_e}), falling back to OVS\n")

# Đường dẫn tới compiled BMv2 JSON
_P4_BUILD    = os.path.join(_REPO_ROOT, "infrastructure", "sdn", "p4", "build")
CORE_JSON    = os.path.join(_P4_BUILD, "core",   "srv6_core.json")
BORDER_JSON  = os.path.join(_P4_BUILD, "border", "srv6_border.json")

_SWITCH_JSON = {
    "core": CORE_JSON,
    "edge": BORDER_JSON,
}

# ══════════════════════════════════════════════════════════════
#  CONFIG K8s
# ══════════════════════════════════════════════════════════════
K8S_SUBNET  = "10.1.0.0/16"
K8S_GATEWAY = "10.1.240.1"   # IP của br-k8s-mn trên host
MN_SUBNET = "10.0.0.0/24"

# Mapping: Mininet IP → bridge-side veth IP (dùng cho return routing)
_MININET_TO_BRIDGE_IP = {
    f"h{i}": (f"10.0.0.{i}", f"10.1.240.{90+i}") for i in range(1, 11)
}

# Quy tắc 2: CPU Pinning (Core độc quyền, Edge chia sẻ)
CPU_PINNING = {
    "s1": 2,  # Hanoi (Core)
    "s2": 3,  # HaiPhong (Core)
    "s3": 6,  # NinhBinh (Edge) - shared
    "s4": 6,  # Vinh (Edge) - shared
    "s5": 6,  # Hue (Edge) - shared
    "s6": 4,  # DaNang (Core)
    "s7": 7,  # QuyNhon (Edge) - shared
    "s8": 7,  # NhaTrang (Edge) - shared
    "s9": 5,  # HoChiMinh (Core)
    "s10": 7, # CanTho (Edge) - shared
}

# Backbone Edges
EDGES = [
    ("s1", "s2"), ("s1", "s3"), ("s3", "s4"), ("s4", "s5"),
    ("s5", "s6"), ("s6", "s7"), ("s7", "s8"), ("s8", "s9"),
    ("s9", "s10"),
    ("s1", "s6"), ("s6", "s9") # Đường trục Bắc-Trung-Nam nhanh
]

# ══════════════════════════════════════════════════════════════

def run_cmd(cmd: str) -> int:
    return subprocess.call(cmd, shell=True)

def run_out(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        return ""

def detect_k8s_bridge():
    if run_out("ip link show cni0"):
        info("*** Detected MicroK8s bridge: cni0\n")
        return "cni0", "microk8s"
    for dev in run_out("ip route show | grep '172.18' | grep -oP 'dev \\K\\S+'").splitlines():
        if dev.startswith("br-"):
            info(f"*** Detected Kind bridge: {dev}\n")
            return dev, "kind"
    info("*** No K8s bridge found (Calico mode). Will create br-k8s-mn\n")
    return "br-k8s-mn", "calico"

def detect_k8s_ip(mode: str) -> str:
    if mode == "kind":
        ip = run_out(
            "docker inspect -f "
            "'{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "
            "nfv-mini-control-plane"
        )
        if ip: return ip
        return "172.18.0.2"
    ip = run_out("hostname -I | awk '{print $1}'")
    if ip: return ip
    return "127.0.0.1"

# ──────────────────────────────────────────────────────────────
#  Topology
# ──────────────────────────────────────────────────────────────

class VietnamTopo(Topo):
    def build(self):
        topo_data = TOPOLOGIES["vietnam"]["nodes"]
        node_coords = {}
        
        # 1. Thêm 10 Switches và Hosts
        for i in range(1, 11):
            s_name = f"s{i}"
            h_name = f"h{i}"
            node_info = topo_data[i-1]
            role = node_info[3]
            msd = node_info[4]
            
            node_coords[s_name] = (node_info[1], node_info[2])
            
            self.addSwitch(s_name, msd=msd, role=role)
            self.addHost(h_name, ip=f"10.0.0.{i}/24", mac=f"00:00:00:00:00:{i:02x}")
            self.addLink(h_name, s_name, delay="0.1ms") # Host to switch

        # 2. Thêm Backbone links với Haversine delay (Quy tắc 3)
        for u, v in EDGES:
            lat1, lon1 = node_coords[u]
            lat2, lon2 = node_coords[v]
            dist = _haversine_km(lat1, lon1, lat2, lon2)
            delay_ms = dist / FIBER_SPEED_KM_PER_MS
            self.addLink(u, v, delay=f"{delay_ms:.2f}ms")

# ──────────────────────────────────────────────────────────────
#  Phase 3/7 — Mininet ↔ K8s bridge
# ──────────────────────────────────────────────────────────────

def _cleanup_old_veths():
    for i in range(1, 11):
        run_cmd(f"ip link delete veth-h{i}-k8s 2>/dev/null")

def _setup_transparent_routing(net, k8s_bridge: str):
    info("*** [Transparent Routing] ip_forward + per-host return routes...\n")
    run_cmd("sysctl -w net.ipv4.ip_forward=1 > /dev/null")
    run_cmd(f"iptables -A FORWARD -i {k8s_bridge} -j ACCEPT 2>/dev/null || true")
    run_cmd(f"iptables -A FORWARD -o {k8s_bridge} -j ACCEPT 2>/dev/null || true")

    for host_name, (mn_ip, bridge_ip) in _MININET_TO_BRIDGE_IP.items():
        run_cmd(f"ip route replace {mn_ip}/32 via {bridge_ip} dev {k8s_bridge} 2>/dev/null || true")
    info("*** [Transparent Routing] Setup complete. NO MASQUERADE. SFC transparency: ON\n")

def setup_bridge(net, k8s_bridge: str, k8s_ip: str, mode: str):
    info(f"*** Setting up Mininet ↔ K8s bridge ({mode})...\n")

    if mode == "calico":
        run_cmd(f"ip link add {k8s_bridge} type bridge 2>/dev/null")
        run_cmd(f"ip addr add {K8S_GATEWAY}/16 dev {k8s_bridge} 2>/dev/null")
        run_cmd(f"ip link set {k8s_bridge} up")
        run_cmd("sysctl -w net.ipv4.ip_forward=1 > /dev/null")

    _cleanup_old_veths()

    subnet = K8S_SUBNET
    gw     = K8S_GATEWAY
    prefix = subnet.split("/")[1]

    # Cấu hình 10 veth pairs cho 10 hosts
    for i in range(1, 11):
        host_name = f"h{i}"
        veth_k8s = f"veth-{host_name}-k8s"
        veth_mn  = f"veth-{host_name}-mn"
        ip       = _MININET_TO_BRIDGE_IP[host_name][1]
        mn_ip    = _MININET_TO_BRIDGE_IP[host_name][0]

        host = net.get(host_name)
        pid  = host.pid

        run_cmd(f"ip link add {veth_k8s} type veth peer name {veth_mn}")
        run_cmd(f"ip link set {veth_k8s} master {k8s_bridge}")
        run_cmd(f"ip link set {veth_k8s} up")
        run_cmd(f"ip link set {veth_mn} netns {pid}")

        host.cmd(f"ip addr add {ip}/{prefix} dev {veth_mn}")
        host.cmd(f"ip link set {veth_mn} up")
        host.cmd(f"ip route add {subnet} via {gw} dev {veth_mn}")

        # L2 Transparent: set src IP
        host.cmd(f"ip route replace default via {gw} dev {veth_mn} src {mn_ip}")

    # Default route từ Host vào Mininet subnet qua h1 (gateway giả)
    h1_k8s_ip = _MININET_TO_BRIDGE_IP["h1"][1]
    run_cmd(f"ip route replace {MN_SUBNET} via {h1_k8s_ip} 2>/dev/null || true")

    # /etc/hosts nội bộ Mininet
    hosts_entries = "".join([f"10.0.0.{i} h{i}\n" for i in range(1, 11)])
    for i in range(1, 11):
        net.get(f"h{i}").cmd(f"printf '{hosts_entries}' >> /etc/hosts")

    _setup_transparent_routing(net, k8s_bridge)
    info("*** Bridge setup complete.\n")

def warm_up(net, k8s_ip: str):
    info("*** Pre-populating ARP/MAC tables...\n")
    for i in range(1, 11):
        net.get(f"h{i}").cmd(f"ping -c 1 {k8s_ip} > /dev/null 2>&1 &")
    time.sleep(2)

# ──────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────

def run_p4(k8s_bridge: str, k8s_ip: str, mode: str):
    if not HAS_P4:
        warn("*** P4 modules not available. Falling back to OVS mode.\n")
        return run_ovs(k8s_bridge, k8s_ip, mode)

    for role, json_path in _SWITCH_JSON.items():
        if not os.path.isfile(json_path):
            warn(f"*** {role} JSON not found: {json_path}\n    Falling back to OVS mode.\n")
            return run_ovs(k8s_bridge, k8s_ip, mode)

    info("*** [Phase 7] Starting 10-node P4RuntimeSwitch topology...\n")

    topo = VietnamTopo()
    # Quy tắc 3: Sử dụng TCLink để áp dụng Haversine delay
    net  = Mininet(topo=topo, switch=OVSBridge, controller=None, link=TCLink)
    net.start()

    manager = SwitchManager(cpu_base=2)
    topo_data = TOPOLOGIES["vietnam"]["nodes"]

    thrift_map = {}
    
    # Gán interface và CPU Pinning (Quy tắc 2)
    for i in range(1, 11):
        s_name = f"s{i}"
        node = net.get(s_name)
        role = topo_data[i-1][3]
        
        interfaces = [(port, intf.name) for port, intf in node.intfs.items() if port != 0]
        
        sw = manager.add_switch(
            name=s_name,
            switch_id=i,
            json_path=_SWITCH_JSON[role],
            interfaces=interfaces,
            cpu_core=CPU_PINNING[s_name],
        )
        thrift_map[s_name] = sw.thrift_port

    if not manager.start_all():
        warn("*** Some P4 switches failed to start! Check docker logs.\n")
    info(manager.status_report() + "\n")

    setup_bridge(net, k8s_bridge, k8s_ip, mode)
    warm_up(net, k8s_ip)

    controller = SDNController(thrift_map)
    info("*** [Phase 7] Waiting for Thrift ports...\n")
    time.sleep(5)

    # Khởi tạo SRv6 Local SIDs cơ bản cho 10 nodes (Routing V6 để trống cho Backend tự đẩy)
    initial_routing = []
    for i in range(1, 11):
        initial_routing.append({
            "switch": f"s{i}", "type": "srv6_sid", "sid": f"fc00:{i}::1"
        })
    controller.bootstrap(initial_routing)

    api_thread = threading.Thread(
        target=start_rest_api, args=(controller, 8765), daemon=True
    )
    api_thread.start()
    info("*** [Phase 7] SDN Controller REST API: http://0.0.0.0:8765\n")

    info("*** 3S-COM Phase 7 Data Plane ready. Type 'exit' to stop.\n")
    CLI(net)

    manager.stop_all()
    net.stop()

def run_ovs(k8s_bridge: str, k8s_ip: str, mode: str):
    info("*** [OVS mode] Starting legacy OVSBridge topology...\n")
    topo = VietnamTopo()
    net  = Mininet(topo=topo, switch=OVSBridge, controller=None, link=TCLink)
    net.start()
    setup_bridge(net, k8s_bridge, k8s_ip, mode)
    warm_up(net, k8s_ip)
    info("*** 3S-COM Data Plane is ready. Type 'exit' to stop.\n")
    CLI(net)
    net.stop()

def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p4", action="store_true", help="Bật Phase 7 P4 mode")
    args, _ = ap.parse_known_args()

    run_cmd("for i in $(ip link show | grep -oE '(s|h)[0-9]+-eth[0-9]+'); do ip link delete $i 2>/dev/null; done")

    k8s_bridge, mode = detect_k8s_bridge()
    k8s_ip           = detect_k8s_ip(mode)

    if args.p4:
        run_p4(k8s_bridge, k8s_ip, mode)
    else:
        run_ovs(k8s_bridge, k8s_ip, mode)

if __name__ == "__main__":
    setLogLevel("info")
    run()
