from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, Controller
from mininet.cli import CLI
from mininet.log import setLogLevel, info

class CoreRouterTopo(Topo):
    def build(self):
        # Switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')

        # Hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        vnf1 = self.addHost('vnf1', ip='10.0.0.11/24', mac='00:00:00:00:00:11')
        vnf2 = self.addHost('vnf2', ip='10.0.0.12/24', mac='00:00:00:00:00:12')

        # Links
        self.addLink(h1, s1)
        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(vnf1, s2)
        self.addLink(vnf2, s3)

def run():
    topo = CoreRouterTopo()
    net = Mininet(topo=topo, controller=Controller)
    net.start()
    
    info('*** 3S-COM Data Plane (Reconstructed) is ready.\n')
    info('*** Thrift ports should be opened externally or via Docker if using BMv2.\n')
    
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
