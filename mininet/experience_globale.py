
import subprocess
import time
from pathlib import Path

from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel

from topologie_iot import IoTTopo


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "baseline"
DURATION = 20


def experiment(net, name, camera_rate, backup_rate):
    folder = RESULTS / name
    folder.mkdir(parents=True, exist_ok=True)

    print(f"\n===== EXPERIENCE : {name.upper()} =====")

    # Les 6 flux reseau
    flows = [
        ("alarme", 5301, ["-u", "-b", "80K", "-l", "160"]),
        ("acces", 5305, ["-u", "-b", "80K", "-l", "160"]),
        ("capteur", 5306, ["-b", "40K"]),
        ("backup", 5304, ["-b", backup_rate]),
        ("camera1", 5302, ["-u", "-b", camera_rate, "-l", "1200"]),
        ("camera2", 5303, ["-u", "-b", camera_rate, "-l", "1200"]),
    ]

    serveur = net.get("serveur")
    server_ip = serveur.IP()

    # Un serveur iperf3 par flux
    servers = []
    for _, port, _ in flows:
        process = serveur.popen(
            ["iperf3", "-s", "-1", "-p", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        servers.append(process)

    time.sleep(1)

    # Demarrer tous les clients sans attendre leur fin
    running = []

    for host_name, port, options in flows:
        output = folder / f"{host_name}.txt"
        file = open(output, "w")

        command = [
            "iperf3", "-c", server_ip,
            "-p", str(port),
            "-t", str(DURATION),
            "-i", "1",
        ] + options

        process = net.get(host_name).popen(
            command,
            stdout=file,
            stderr=subprocess.STDOUT
        )

        running.append((host_name, process, file, output))

    # Mesure complementaire du RTT ICMP de l'alarme
    ping_file = open(folder / "ping_alarme.txt", "w")

    ping = net.get("alarme").popen(
        ["ping", "-c", "90", "-i", "0.2", server_ip],
        stdout=ping_file,
        stderr=subprocess.STDOUT
    )

    # Attendre la fin des mesures
    for _, process, file, _ in running:
        process.wait()
        file.close()

    ping.wait()
    ping_file.close()

    for server in servers:
        if server.poll() is None:
            server.terminate()

    # Afficher les resumes
    print("\n--- RESULTATS DES FLUX ---")

    for host_name, _, _, output in running:
        lines = output.read_text().splitlines()

        summaries = [
            line.strip()
            for line in lines
            if "receiver" in line or "sender" in line
        ]

        print(f"\n{host_name} :")
        for line in (summaries[-2:] if summaries else lines[-4:]):
            print(line)

    print("\n--- RTT ALARME ---")
    ping_lines = (folder / "ping_alarme.txt").read_text().splitlines()

    for line in ping_lines[-4:]:
        print(line)

    print(f"\nResultats sauvegardes dans : {folder}")


if __name__ == "__main__":
    setLogLevel("warning")

    net = Mininet(
        topo=IoTTopo(),
        controller=None,
        switch=OVSBridge,
        link=TCLink,
        autoSetMacs=True
    )

    try:
        net.start()

        experiment(
            net,
            name="normal",
            camera_rate="2M",
            backup_rate="2M"
        )

        time.sleep(3)

        experiment(
            net,
            name="congestion",
            camera_rate="6M",
            backup_rate="5M"
        )

    finally:
        net.stop()

    print("\nExperiences terminees.")
