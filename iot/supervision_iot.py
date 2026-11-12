
import json
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"
TOPIC = "batiment/#"

ROOT = Path(__file__).resolve().parent.parent
FICHIER = ROOT / "results/mqtt/evenements_iot.csv"
FICHIER.parent.mkdir(parents=True, exist_ok=True)

COLONNES = [
    "date_reception",
    "topic",
    "device_id",
    "seq",
    "event",
    "temperature",
    "humidity",
    "badge",
    "decision",
    "delai_ms"
]


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Supervision MQTT connectee !", flush=True)
        client.subscribe(TOPIC, qos=1)
        print("Ecoute de tous les topics du batiment", flush=True)
    else:
        print(f"Erreur de connexion : {reason_code}", flush=True)


def on_message(client, userdata, msg):
    reception_ns = time.time_ns()

    try:
        data = json.loads(msg.payload.decode("utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Le message doit etre un objet JSON")

    except (ValueError, UnicodeDecodeError):
        print(f"Message non JSON sur {msg.topic}", flush=True)
        return

    # Calcul du delai pour les publications horodatees
    delai_ms = ""

    if msg.topic in ("batiment/alarme", "batiment/capteur"):
        envoi_ns = data.get("sent_ns")

        if isinstance(envoi_ns, int):
            delai_ms = round(
                (reception_ns - envoi_ns) / 1_000_000,
                3
            )

    date_reception = datetime.fromtimestamp(
        reception_ns / 1_000_000_000,
        tz=timezone.utc
    ).isoformat()

    ligne = {
        "date_reception": date_reception,
        "topic": msg.topic,
        "device_id": data.get("device_id", ""),
        "seq": data.get("seq", ""),
        "event": data.get("event", data.get("action", "")),
        "temperature": data.get("temperature", ""),
        "humidity": data.get("humidity", ""),
        "badge": data.get("badge", ""),
        "decision": data.get("decision", ""),
        "delai_ms": delai_ms
    }

    nouveau = not FICHIER.exists() or FICHIER.stat().st_size == 0

    with open(FICHIER, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES)

        if nouveau:
            writer.writeheader()

        writer.writerow(ligne)

    print(
        f"[{msg.topic}] "
        f"Equipement={ligne['device_id']} "
        f"Seq={ligne['seq']} "
        f"Delai={delai_ms} ms",
        flush=True
    )


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="supervision_centrale_iot"
)

client.on_connect = on_connect
client.on_message = on_message

print("Demarrage de la supervision IoT...", flush=True)

client.connect(BROKER, 1883, 60)
client.loop_forever()
