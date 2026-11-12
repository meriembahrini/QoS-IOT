
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


class IoTTopo(Topo):

    def build(self):

        # Deux switchs Open vSwitch
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        # Objets IoT : nom, adresse IP
        objets = [
            ('alarme', '10.0.0.1'),
            ('acces', '10.0.0.2'),
            ('capteur', '10.0.0.3'),
            ('backup', '10.0.0.4'),
            ('camera1', '10.0.0.5'),
            ('camera2', '10.0.0.6')
        ]

        # Connexion des objets au switch S1
        for nom, ip in objets:
            self.addHost(nom, ip=f'{ip}/24')
            self.addLink(nom, s1)

        # Serveur IoT et supervision sur S2
        self.addHost('serveur', ip='10.0.0.7/24')
        self.addHost('monitor', ip='10.0.0.8/24')

        self.addLink('serveur', s2)
        self.addLink('monitor', s2)

        # Lien principal limite a 10 Mbit/s
        self.addLink(
            s1, s2,
            bw=10,
            delay='5ms',
            max_queue_size=100
        )


if __name__ == '__main__':

    setLogLevel('info')

    net = Mininet(
        topo=IoTTopo(),
        controller=None,
        switch=OVSBridge,
        link=TCLink,
        autoSetMacs=True
    )

    try:
        net.start()
        print("\nReseau IoT operationnel !")
        CLI(net)
    finally:
        net.stop()
