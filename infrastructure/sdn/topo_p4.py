from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, OVSController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import subprocess
import sys
import time

# ══════════════════════════════════════════════════════════════
#  CONFIG — Tự động nhận diện môi trường (Kind hay MicroK8s)
# ══════════════════════════════════════════════════════════════
# Địa chỉ ảo mà các Mininet host sẽ dùng để nối vào K8s network
VNF1_MN_IP  = "10.0.0.11"
VNF1_K8S_IP = "10.1.240.91"   # IP trong dải Pod MicroK8s (10.1.0.0/16)
VNF2_K8S_IP = "10.1.240.92"
H1_K8S_IP   = "10.1.240.90"
K8S_SUBNET  = "10.1.0.0/16"   # Dải IP Pod của MicroK8s
K8S_GATEWAY = "10.1.240.1"    # Gateway để đi vào K8s cluster

def run_cmd(cmd):
    subprocess.call(cmd, shell=True)

def detect_k8s_bridge():
    """Tự động tìm bridge của K8s.
    - MicroK8s (default): cni0
    - Kind: br-xxxxxxxxxx
    - Calico/Custom: Sẽ tự tạo 'br-k8s-mn' nếu không tìm thấy.
    """
    # 1. Thử MicroK8s cni0
    try:
        subprocess.check_output("ip link show cni0", shell=True)
        info("*** Detected MicroK8s bridge: cni0\n")
        return "cni0", "microk8s"
    except:
        pass

    # 2. Thử Kind bridge
    try:
        out = subprocess.check_output(
            "ip route show | grep '172.18' | grep -oP 'dev \\K\\S+'",
            shell=True
        ).decode().strip().splitlines()
        for dev in out:
            if dev.startswith("br-"):
                info(f"*** Detected Kind bridge: {dev}\n")
                return dev, "kind"
    except:
        pass

    # 3. Không thấy bridge nào -> Yêu cầu tự tạo bridge ảo
    info("*** No K8s bridge found (likely Calico). Using custom bridge: br-k8s-mn\n")
    return "br-k8s-mn", "calico"

def detect_k8s_ip(mode="microk8s"):
    """Lấy IP NodePort của K8s để test healthz."""
    if mode == "kind":
        try:
            ip = subprocess.check_output(
                "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' nfv-mini-control-plane",
                shell=True
            ).decode().strip()
            if ip:
                info(f"*** Kind IP: {ip}\n")
                return ip
        except:
            pass
        return "172.18.0.2"
    else:
        # MicroK8s: IP chính của server (Pod traffic ra ngoài qua host)
        try:
            ip = subprocess.check_output(
                "hostname -I | awk '{print $1}'",
                shell=True
            ).decode().strip()
            if ip:
                info(f"*** MicroK8s Host IP: {ip}\n")
                return ip
        except:
            pass
        return "127.0.0.1"

class CoreRouterTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')

        h1   = self.addHost('h1',   ip='10.0.0.1/24',  mac='00:00:00:00:00:01')
        vnf1 = self.addHost('vnf1', ip='10.0.0.11/24', mac='00:00:00:00:00:11')
        vnf2 = self.addHost('vnf2', ip='10.0.0.12/24', mac='00:00:00:00:00:12')

        self.addLink(h1, s1)
        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(vnf1, s2)
        self.addLink(vnf2, s3)

def setup_bridge(net, k8s_bridge, k8s_ip, mode):
    info(f"*** Setting up Mininet <-> K8s bridge ({mode})...\n")

    # Nếu là Calico/Custom, ta phải tự tạo bridge trên Host
    if mode == "calico":
        run_cmd(f"ip link add {k8s_bridge} type bridge 2>/dev/null")
        run_cmd(f"ip addr add {K8S_GATEWAY}/16 dev {k8s_bridge} 2>/dev/null")
        run_cmd(f"ip link set {k8s_bridge} up")
        run_cmd("sysctl -w net.ipv4.ip_forward=1 > /dev/null")

    # Xóa các veth cũ nếu còn sót
    for veth in ["veth-h1-k8s", "veth-vnf1-k8s", "veth-vnf2-k8s"]:
        run_cmd("ip link delete " + veth + " 2>/dev/null")

    if mode == "kind":
        subnet = "172.18.0.0/16"
        gw     = "172.18.0.1"
        configs = [
            ("h1",   "veth-h1-k8s",   "veth-h1-mn",   "172.18.0.90"),
            ("vnf1", "veth-vnf1-k8s", "veth-vnf1-mn", "172.18.0.91"),
            ("vnf2", "veth-vnf2-k8s", "veth-vnf2-mn", "172.18.0.92"),
        ]
        # Route ngược từ Kind container vào Mininet
        run_cmd(f'docker exec nfv-mini-control-plane ip route add 10.0.0.0/24 via 172.18.0.91 2>/dev/null || true')
    else:
        subnet = K8S_SUBNET
        gw     = K8S_GATEWAY
        configs = [
            ("h1",   "veth-h1-k8s",   "veth-h1-mn",   H1_K8S_IP),
            ("vnf1", "veth-vnf1-k8s", "veth-vnf1-mn", VNF1_K8S_IP),
            ("vnf2", "veth-vnf2-k8s", "veth-vnf2-mn", VNF2_K8S_IP),
        ]
        # Route từ Host Server vào Mininet qua vnf1
        run_cmd(f'ip route replace 10.0.0.0/24 via {VNF1_K8S_IP} 2>/dev/null || true')

    for host_name, veth_k8s, veth_mn, ip in configs:
        host = net.get(host_name)
        pid  = host.pid

        run_cmd(f'ip link add {veth_k8s} type veth peer name {veth_mn}')
        run_cmd(f'ip link set {veth_k8s} master {k8s_bridge}')
        run_cmd(f'ip link set {veth_k8s} up')
        run_cmd(f'ip link set {veth_mn} netns {pid}')

        prefix = subnet.split("/")[1]
        host.cmd(f'ip addr add {ip}/{prefix} dev {veth_mn}')
        host.cmd(f'ip link set {veth_mn} up')
        host.cmd(f'ip route add {subnet} via {gw} dev {veth_mn}')
        info(f"    {host_name} -> {ip} OK\n")

    # Thêm /etc/hosts để resolve nội bộ
    hosts_lines = "10.0.0.1 h1\\n10.0.0.11 vnf1\\n10.0.0.12 vnf2\\n"
    for host_name in ["h1", "vnf1", "vnf2"]:
        host = net.get(host_name)
        host.cmd("echo '" + hosts_lines + "' >> /etc/hosts")

    info("*** Bridge setup complete.\n")
    info(f"*** Test: vnf1 curl -sS http://{k8s_ip}:31656/healthz\n")

def warm_up(net, k8s_ip):
    """Prime OVS MAC tables và ARP cache để tránh packet loss lần đầu."""
    info("*** Pre-populating ARP tables...\n")
    h1 = net.get('h1')
    vnf1 = net.get('vnf1')
    vnf2 = net.get('vnf2')
    h1.cmd('ping -c 1 10.0.0.11 > /dev/null 2>&1 &')
    h1.cmd(f'ping -c 1 {k8s_ip} > /dev/null 2>&1 &')
    vnf1.cmd(f'ping -c 1 {k8s_ip} > /dev/null 2>&1 &')
    vnf2.cmd(f'ping -c 1 {k8s_ip} > /dev/null 2>&1 &')
    time.sleep(2)

def run():
    k8s_bridge, mode = detect_k8s_bridge()
    k8s_ip = detect_k8s_ip(mode)

    topo = CoreRouterTopo()
    from mininet.node import OVSBridge
    net = Mininet(topo=topo, switch=OVSBridge, controller=None)
    net.start()

    setup_bridge(net, k8s_bridge, k8s_ip, mode)
    warm_up(net, k8s_ip)

    info('*** 3S-COM Data Plane is ready.\n')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
