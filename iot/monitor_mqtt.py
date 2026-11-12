
import json
import csv
import time
from pathlib import Path
import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"
TOPIC = "batiment/alarme"

RESULTATS = Path(__file__).resolve().parent.parent / "results/mqtt"
RESULTATS.mkdir(parents=True, exist_ok=True)

FICHIER = RESULTATS / "alertes.csv"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connecte au broker MQTT !", flush=True)
        client.subscribe(TOPIC, qos=1)
        print(f"En ecoute sur : {TOPIC}", flush=True)
    else:
        print(f"Echec de connexion : {reason_code}", flush=True)


def on_message(client, userdata, msg):
    reception_ns = time.time_ns()

    data = json.loads(msg.payload.decode("utf-8"))

    numero = data.get("seq", "")
    evenement = data.get("event", "INCONNU")
    envoi_ns = data.get("sent_ns")

    delai_ms = None
    if isinstance(envoi_ns, int):
        delai_ms = (reception_ns - envoi_ns) / 1_000_000

    print(f"\nMessage recu : {evenement}")
    print(f"Numero de sequence : {numero}")
    print(f"Delai MQTT : {delai_ms} ms", flush=True)

    nouveau = not FICHIER.exists()

    with open(FICHIER, "a", newline="") as f:
        writer = csv.writer(f)

        if nouveau:
            writer.writerow(["sequence", "evenement", "delai_ms"])

        writer.writerow([numero, evenement, delai_ms])


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="monitor_iot"
)

client.on_connect = on_connect
client.on_message = on_message

print("Demarrage du moniteur MQTT...", flush=True)

client.connect(BROKER, 1883, 60)
client.loop_forever()
