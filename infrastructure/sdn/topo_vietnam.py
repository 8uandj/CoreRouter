#!/usr/bin/env python3
"""
topo_vietnam.py — Vietnam Backbone (10-node) for Phase 4
Mạng trục 10 node Việt Nam tích hợp MicroK8s trên Server 112.137.129.246.
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import subprocess
import time
import os

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION (Tương ứng với src/orchestration/jo_vdpr/topology.py)
# ══════════════════════════════════════════════════════════════
NODES = [
    ("Hanoi",      "s1",  "core", 10),
    ("HaiPhong",   "s2",  "core", 10),
    ("NinhBinh",   "s3",  "edge", 5),
    ("Vinh",       "s4",  "edge", 5),
    ("Hue",        "s5",  "edge", 4),
    ("DaNang",     "s6",  "core", 8),
    ("QuyNhon",    "s7",  "edge", 4),
    ("NhaTrang",   "s8",  "edge", 5),
    ("HoChiMinh",  "s9",  "core", 10),
    ("CanTho",     "s10", "edge", 5),
]

# Danh sách các liên kết trục (Backbone Edges)
EDGES = [
    ("s1", "s2"), ("s1", "s3"), ("s3", "s4"), ("s4", "s5"),
    ("s5", "s6"), ("s6", "s7"), ("s7", "s8"), ("s8", "s9"),
    ("s9", "s10"),
    ("s1", "s6"), ("s6", "s9") # Đường trục Bắc-Trung-Nam nhanh
]

# ══════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════

def run_cmd(cmd):
    return subprocess.call(cmd, shell=True)

def detect_k8s_bridge():
    """Tự động tìm CNI bridge của MicroK8s (thường là cni0)."""
    try:
        # MicroK8s mặc định dùng 10.1.0.0/16 cho pods
        out = subprocess.check_output(
            "ip route show | grep '10.1.' | grep -oP 'dev \\K\\S+'",
            shell=True
        ).decode().strip().splitlines()
        for dev in out:
            if dev.startswith("cni0") or dev.startswith("cali"):
                info(f"*** Auto-detected K8s bridge: {dev}\n")
                return dev
    except:
        pass
    info("*** Defaulting to cni0\n")
    return "cni0"

def detect_node_ip():
    """Lấy IP của chính server để làm gateway cho Mininet."""
    try:
        ip = subprocess.check_output("hostname -I", shell=True).decode().split()[0]
        info(f"*** Auto-detected Host IP: {ip}\n")
        return ip
    except:
        return "127.0.0.1"

# ══════════════════════════════════════════════════════════════
#  TOPOLOGY CLASS
# ══════════════════════════════════════════════════════════════

class VietnamTopo(Topo):
    def build(self):
        switches = {}
        # 1. Thêm Switches (P4-ready structure)
        for name, sid, role, msd in NODES:
            # Gán MSD vào tham số để Backend có thể query sau này
            sw = self.addSwitch(sid, msd=msd, role=role)
            switches[sid] = sw
            
            # 2. Thêm Host tại mỗi node để test
            # Node 1 (Hanoi) sẽ là điểm Ingress chính (h1)
            # Node 9 (HCM) sẽ là điểm Egress chính (h9)
            h_name = "h" + sid[1:]
            self.addHost(h_name, ip=f"10.0.0.{sid[1:]}/24")
            self.addLink(h_name, sw)

        # 3. Thêm các liên kết xương sống
        for u, v in EDGES:
            self.addLink(u, v)

def setup_microk8s_bridge(net, bridge_iface, host_ip):
    info(f"*** Bridging Mininet to MicroK8s via {bridge_iface}...\n")
    
    # Chúng ta sẽ bridge h1 (Hanoi) vào K8s để giả lập traffic đi vào từ miền Bắc
    h1 = net.get('h1')
    pid = h1.pid
    veth_kind = "veth-h1-k8s"
    veth_mn = "veth-h1-mn"
    
    run_cmd(f"ip link delete {veth_kind} 2>/dev/null")
    run_cmd(f"ip link add {veth_kind} type veth peer name {veth_mn}")
    run_cmd(f"ip link set {veth_kind} master {bridge_iface}")
    run_cmd(f"ip link set {veth_kind} up")
    run_cmd(f"ip link set {veth_mn} netns {pid}")
    
    # Gán IP trong dải pod của K8s (giả sử dải 10.1.x.x)
    # Chúng ta chọn một IP tĩnh 10.1.254.1 cho h1
    h1.cmd("ip addr add 10.1.254.1/16 dev veth-h1-mn")
    h1.cmd("ip link set veth-h1-mn up")
    
    # Route traffic 10.0.0.0/24 từ Host vào Mininet qua h1
    run_cmd(f"ip route add 10.0.0.0/24 via 10.1.254.1 2>/dev/null || true")
    
    info(f"    h1 (Hanoi) connected to K8s as 10.1.254.1 OK\n")

def run():
    k8s_bridge = detect_k8s_bridge()
    host_ip = detect_node_ip()

    topo = VietnamTopo()
    # Sử dụng OVSBridge để tối giản, Phase 5 sẽ nâng cấp lên P4Runtime
    net = Mininet(topo=topo, switch=OVSBridge, controller=None)
    net.start()
    
    setup_microk8s_bridge(net, k8s_bridge, host_ip)

    info('*** Vietnam 10-node Backbone is ready.\n')
    info('*** Test: h1 ping 10.1.0.1 (K8s API) or check VNF services\n')
    
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    if os.getuid() != 0:
        print("Lỗi: Script này yêu cầu quyền sudo.")
        exit(1)
    run()
