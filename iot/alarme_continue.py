import argparse
import json
import os
import time
from threading import Event

import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"
TOPIC = "batiment/alarme"

parser = argparse.ArgumentParser()
parser.add_argument("--duree", type=int, default=40)
parser.add_argument("--intervalle", type=float, default=1.0)
args = parser.parse_args()

connexion = Event()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        connexion.set()
        print("[ALARME] MQTT connecte", flush=True)
    else:
        print(f"[ALARME] Erreur MQTT : {reason_code}", flush=True)


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"sonde_alarme_{os.getpid()}"
)

client.on_connect = on_connect

client.connect(BROKER, 1883, 60)
client.loop_start()
if not connexion.wait(timeout=5):
    client.disconnect()
    client.loop_stop()
    raise RuntimeError("Connexion MQTT impossible")

debut = time.monotonic()
numero = 0

try:
    while time.monotonic() - debut < args.duree:

        numero += 1

        message = {
            "device_id": "alarme_01",
            "seq": numero,
            "event": "HEARTBEAT",
            "sent_ns": time.time_ns()
        }

        resultat = client.publish(
            TOPIC,
            json.dumps(message),
            qos=1
        )

        resultat.wait_for_publish(timeout=3)

        print(
            f"[ALARME] Message {numero} publie",
            flush=True
        )

        restant = args.duree - (time.monotonic() - debut)
        if restant > 0:
            time.sleep(min(args.intervalle, restant))

finally:
    client.disconnect()
    client.loop_stop()

print(
    f"[ALARME] Termine : {numero} messages",
    flush=True
)
