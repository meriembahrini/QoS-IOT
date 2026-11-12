
import json
import csv
import time
from threading import Event
from pathlib import Path

import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"
TOPIC_DEMANDE = "batiment/acces/demande"
TOPIC_REPONSE = "batiment/acces/reponse"

FICHIER = Path("results/mqtt/acces.csv")
FICHIER.parent.mkdir(parents=True, exist_ok=True)

connecte = Event()
abonne = Event()
reponse_recue = Event()

sequence_attendue = None
derniere_reponse = {}


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Porte connectee au broker MQTT !", flush=True)
        connecte.set()
        client.subscribe(TOPIC_REPONSE, qos=1)


def on_subscribe(client, userdata, mid, reason_codes, properties):
    if any(code.is_failure for code in reason_codes):
        print("Abonnement refuse", flush=True)
        return

    print("Abonnement aux reponses actif", flush=True)
    abonne.set()


def on_message(client, userdata, msg):
    reception_ns = time.monotonic_ns()

    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return

    if data.get("seq") != sequence_attendue:
        return

    if data.get("device_id") != "porte_01":
        return

    derniere_reponse.clear()
    derniere_reponse.update(data)
    derniere_reponse["reception_ns"] = reception_ns

    reponse_recue.set()


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="porte_01"
)

client.on_connect = on_connect
client.on_subscribe = on_subscribe
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_start()

if not connecte.wait(timeout=5):
    raise RuntimeError("Connexion MQTT impossible")

if not abonne.wait(timeout=5):
    raise RuntimeError("Abonnement MQTT impossible")

nouveau = not FICHIER.exists()

with open(FICHIER, "a", newline="") as fichier:
    writer = csv.writer(fichier)

    if nouveau:
        writer.writerow(["sequence", "badge", "decision", "rtt_ms"])

    for seq, badge in [(1, "1024"), (2, "9999")]:
        sequence_attendue = seq
        reponse_recue.clear()

        envoi_ns = time.monotonic_ns()

        demande = {
            "device_id": "porte_01",
            "badge": badge,
            "seq": seq,
            "sent_ns": envoi_ns
        }

        resultat = client.publish(
            TOPIC_DEMANDE,
            json.dumps(demande),
            qos=1
        )

        if resultat.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("Echec de publication MQTT")

        print(f"\nDemande envoyee : badge {badge}", flush=True)

        if not reponse_recue.wait(timeout=5):
            print("ERREUR : aucune reponse recue", flush=True)
            writer.writerow([seq, badge, "TIMEOUT", ""])
            continue

        if derniere_reponse.get("request_sent_ns") != envoi_ns:
            print("ERREUR : reponse non associee a la demande")
            continue

        delai_ms = (
            derniere_reponse["reception_ns"] - envoi_ns
        ) / 1_000_000

        decision = derniere_reponse["decision"]

        print(f"Decision : {decision}", flush=True)
        print(f"Temps de reponse : {delai_ms:.3f} ms", flush=True)

        writer.writerow([seq, badge, decision, round(delai_ms, 3)])

        time.sleep(1)

client.disconnect()
client.loop_stop()

print("\nFin du test de controle d'acces.")
