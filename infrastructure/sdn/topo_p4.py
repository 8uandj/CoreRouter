"""
3S-COM Testbed — Data Plane (Phase 3: Mininet ↔ K8s NodePort Bridge)
=====================================================================
Topology:
    h1 ── s1 ── s2 ── s3
                │      │
              vnf1    vnf2

Bridge mode (Calico / MicroK8s):
    Mỗi host có thêm veth nối vào br-k8s-mn → host kernel → K8s NodePort.
    Tất cả host đều có default route qua br-k8s-mn để reach NodePort.

Usage:
    sudo python3 infrastructure/sdn/topo_p4.py
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import subprocess
import sys
import time

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


def _ensure_masquerade(src_subnet: str):
    """Đảm bảo iptables MASQUERADE rule tồn tại cho subnet Mininet.

    Cho phép traffic từ Mininet hosts reach NodePort bên ngoài
    (ví dụ: 10.10.x.x) mà không bị drop.
    """
    # Kiểm tra xem rule đã tồn tại chưa
    check = run_out(
        f"iptables -t nat -C POSTROUTING -s {src_subnet} ! -d {src_subnet} -j MASQUERADE 2>&1"
    )
    if "No chain/target" in check or check == "":
        run_cmd(f"iptables -t nat -A POSTROUTING -s {src_subnet} ! -d {src_subnet} -j MASQUERADE")
        run_cmd(f"iptables -A FORWARD -s {src_subnet} -j ACCEPT")
        run_cmd(f"iptables -A FORWARD -d {src_subnet} -j ACCEPT")
        info(f"*** MASQUERADE rule added for {src_subnet}\n")


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

        run_cmd(f"ip link add {veth_k8s} type veth peer name {veth_mn}")
        run_cmd(f"ip link set {veth_k8s} master {k8s_bridge}")
        run_cmd(f"ip link set {veth_k8s} up")
        run_cmd(f"ip link set {veth_mn} netns {pid}")

        host.cmd(f"ip addr add {ip}/{prefix} dev {veth_mn}")
        host.cmd(f"ip link set {veth_mn} up")
        host.cmd(f"ip route add {subnet} via {gw} dev {veth_mn}")
        # Default route: cho phép reach bất kỳ IP nào (NodePort, internet)
        host.cmd(f"ip route add default via {gw} dev {veth_mn} 2>/dev/null || true")
        info(f"    {host_name} → {ip} OK\n")

    # /etc/hosts nội bộ Mininet
    hosts_entries = "10.0.0.1 h1\n10.0.0.11 vnf1\n10.0.0.12 vnf2\n"
    for host_name in ["h1", "vnf1", "vnf2"]:
        net.get(host_name).cmd(f"printf '{hosts_entries}' >> /etc/hosts")

    # Đảm bảo MASQUERADE cho Mininet subnet
    _ensure_masquerade(MN_SUBNET)

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

def run():
    k8s_bridge, mode = detect_k8s_bridge()
    k8s_ip           = detect_k8s_ip(mode)

    topo = CoreRouterTopo()
    net  = Mininet(topo=topo, switch=OVSBridge, controller=None)
    net.start()

    setup_bridge(net, k8s_bridge, k8s_ip, mode)
    warm_up(net, k8s_ip)
    verify_phase3(net, k8s_ip)

    info("*** 3S-COM Data Plane is ready. Type 'exit' to stop.\n")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
