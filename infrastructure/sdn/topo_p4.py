from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, OVSController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import subprocess
import sys
import time

KIND_CONTAINER = "nfv-mini-control-plane"
VNF1_MN_IP     = "10.0.0.11"
VNF1_KIND_IP   = "172.18.0.91"
VNF2_KIND_IP   = "172.18.0.92"
H1_KIND_IP     = "172.18.0.90"

def run_cmd(cmd):
    subprocess.call(cmd, shell=True)

def detect_kind_bridge():
    """Tu dong tim ten Docker bridge cua Kind."""
    try:
        out = subprocess.check_output(
            "ip route show | grep '172.18' | grep -oP 'dev \\K\\S+'",
            shell=True
        ).decode().strip().splitlines()
        for dev in out:
            if dev.startswith("br-"):
                info(f"*** Auto-detected Kind bridge: {dev}\n")
                return dev
    except:
        pass
    info("*** Defaulting to br-81baf1727d77\n")
    return "br-81baf1727d77"

def detect_kind_ip():
    try:
        ip = subprocess.check_output(
            "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' " + KIND_CONTAINER,
            shell=True
        ).decode().strip()
        if ip:
            info(f"*** Auto-detected Kind IP: {ip}\n")
            return ip
    except:
        pass
    return "172.18.0.2"

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

def setup_bridge(net, kind_bridge, kind_ip):
    info("*** Setting up Mininet <-> Kind bridge...\n")

    for veth in ["veth-h1-kind", "veth-vnf1-kind", "veth-vnf2-kind"]:
        run_cmd("ip link delete " + veth + " 2>/dev/null")

    configs = [
        ("h1",   "veth-h1-kind",   "veth-h1-mn",   H1_KIND_IP),
        ("vnf1", "veth-vnf1-kind", "veth-vnf1-mn", VNF1_KIND_IP),
        ("vnf2", "veth-vnf2-kind", "veth-vnf2-mn", VNF2_KIND_IP),
    ]

    for host_name, veth_kind, veth_mn, ip in configs:
        host = net.get(host_name)
        pid  = host.pid

        run_cmd(f'ip link add {veth_kind} type veth peer name {veth_mn}')
        run_cmd(f'ip link set {veth_kind} master {kind_bridge}')
        run_cmd(f'ip link set {veth_kind} up')
        run_cmd(f'ip link set {veth_mn} netns {pid}')

        host.cmd(f'ip addr add {ip}/16 dev {veth_mn}')
        host.cmd(f'ip link set {veth_mn} up')
        host.cmd(f'ip route add 172.18.0.0/16 via 172.18.0.1')
        info(f"    {host_name} -> {ip} OK\n")

    run_cmd(f'docker exec {KIND_CONTAINER} ip route add 10.0.0.0/24 via {VNF1_KIND_IP} 2>/dev/null || true')
    info(f"    Kind -> 10.0.0.0/24 via {VNF1_KIND_IP} OK\n")

    # Thêm /etc/hosts để resolve nội bộ
    hosts_lines = "10.0.0.1 h1\\n10.0.0.11 vnf1\\n10.0.0.12 vnf2\\n"
    for host_name in ["h1", "vnf1", "vnf2"]:
        host = net.get(host_name)
        host.cmd("echo '" + hosts_lines + "' >> /etc/hosts")

    info("*** Bridge setup complete.\n")
    info("*** Test: vnf1 curl -sS http://" + kind_ip + ":31656/healthz\n")

def warm_up(net, kind_ip):
    """Prime OVS MAC tables và ARP cache để tránh packet loss lần đầu."""
    info("*** Pre-populating ARP tables...\n")
    h1 = net.get('h1')
    vnf1 = net.get('vnf1')
    vnf2 = net.get('vnf2')
    h1.cmd('ping -c 1 10.0.0.11 > /dev/null 2>&1 &')
    h1.cmd(f'ping -c 1 {kind_ip} > /dev/null 2>&1 &')
    vnf1.cmd(f'ping -c 1 {kind_ip} > /dev/null 2>&1 &')
    vnf2.cmd(f'ping -c 1 {kind_ip} > /dev/null 2>&1 &')
    time.sleep(2)

def run():
    kind_bridge = detect_kind_bridge()
    kind_ip     = detect_kind_ip()

    topo = CoreRouterTopo()
    # Use OVSController for fast learning to avoid drop
    net = Mininet(topo=topo, controller=OVSController)
    net.start()
    
    setup_bridge(net, kind_bridge, kind_ip)
    warm_up(net, kind_ip)

    info('*** 3S-COM Data Plane is ready.\n')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
