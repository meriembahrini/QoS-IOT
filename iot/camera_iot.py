
import argparse
import json
import subprocess
import time

from pathlib import Path
from threading import Event, Lock

import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"
TOPIC = "batiment/securite/evenements"

# Port iperf3 propre a chaque camera
PORTS = {
    "camera1": 5302,
    "camera2": 5303
}

# Debits selon l'etat de la camera
DEBITS = {
    "VEILLE": "500K",
    "ALERTE": "6M"
}

parser = argparse.ArgumentParser()
parser.add_argument("--camera", choices=PORTS, required=True)
parser.add_argument("--duree", type=int, default=180)
args = parser.parse_args()

NOM = args.camera
PORT = PORTS[NOM]

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "results" / "cameras"
DOSSIER.mkdir(parents=True, exist_ok=True)

LOG_IPERF = DOSSIER / f"{NOM}_iperf.log"

etat = {"mode": "VEILLE"}
verrou = Lock()
abonnement_actif = Event()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[{NOM}] MQTT connecte", flush=True)
        client.subscribe(TOPIC, qos=1)
    else:
        print(f"[{NOM}] Erreur MQTT : {reason_code}", flush=True)


def on_subscribe(client, userdata, mid, reason_codes, properties):
    if any(code.is_failure for code in reason_codes):
        print(f"[{NOM}] Abonnement refuse", flush=True)
        return

    abonnement_actif.set()
    print(f"[{NOM}] Abonnement actif", flush=True)


def on_message(client, userdata, msg):
    try:
        message = json.loads(msg.payload.decode("utf-8"))
        evenement = message.get("event")
    except (ValueError, UnicodeDecodeError, AttributeError):
        return

    with verrou:
        if evenement == "INTRUSION_DETECTED":
            etat["mode"] = "ALERTE"
            print(f"[{NOM}] INTRUSION !", flush=True)

        elif evenement == "RETURN_TO_NORMAL":
            etat["mode"] = "VEILLE"
            print(f"[{NOM}] Retour au mode veille", flush=True)


def demarrer_flux(mode, fichier):
    debit = DEBITS[mode]

    print(
        f"[{NOM}] Mode {mode} : {debit}",
        flush=True
    )

    fichier.write(f"\n=== {NOM} - MODE {mode} ===\n")
    fichier.flush()

    commande = [
        "iperf3",
        "-c", BROKER,
        "-p", str(PORT),
        "-u",
        "-b", debit,
        "-l", "1200",
        "-t", "300",
        "-i", "1",
        "--forceflush"
    ]

    return subprocess.Popen(
        commande,
        stdout=fichier,
        stderr=subprocess.STDOUT
    )


def arreter_flux(processus):
    if processus is None:
        return

    if processus.poll() is None:
        processus.terminate()

        try:
            processus.wait(timeout=3)
        except subprocess.TimeoutExpired:
            processus.kill()
            processus.wait()


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"{NOM}_iot"
)

client.on_connect = on_connect
client.on_subscribe = on_subscribe
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_start()

if not abonnement_actif.wait(timeout=5):
    client.disconnect()
    client.loop_stop()
    raise RuntimeError("Abonnement MQTT non etabli")

processus = None
mode_actuel = None

try:
    debut = time.monotonic()

    with open(LOG_IPERF, "a", buffering=1) as fichier:

        while time.monotonic() - debut < args.duree:

            with verrou:
                mode_demande = etat["mode"]

            if (
                mode_demande != mode_actuel
                or processus is None
                or processus.poll() is not None
            ):
                arreter_flux(processus)

                processus = demarrer_flux(
                    mode_demande,
                    fichier
                )

                mode_actuel = mode_demande

            time.sleep(0.2)

except KeyboardInterrupt:
    print(f"[{NOM}] Arret demande", flush=True)

finally:
    arreter_flux(processus)
    client.disconnect()
    client.loop_stop()
    print(f"[{NOM}] Simulation terminee", flush=True)
