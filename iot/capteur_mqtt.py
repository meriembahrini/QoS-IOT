
import json
import time
from threading import Event
import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"
TOPIC = "batiment/capteur"

connecte = Event()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Capteur connecte au broker MQTT !", flush=True)
        connecte.set()
    else:
        print(f"Erreur MQTT : {reason_code}", flush=True)


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="capteur_01"
)

client.on_connect = on_connect

client.connect(BROKER, 1883, 60)
client.loop_start()

if not connecte.wait(timeout=5):
    raise RuntimeError("Connexion MQTT impossible")

# Mesures simulees du capteur
temperatures = [23.5, 23.8, 24.1, 24.3]
humidites = [48, 47, 47, 46]

for seq in range(1, 5):

    message = {
        "device_id": "capteur_01",
        "seq": seq,
        "temperature": temperatures[seq - 1],
        "humidity": humidites[seq - 1],
        "sent_ns": time.time_ns()
    }

    resultat = client.publish(
        TOPIC,
        json.dumps(message),
        qos=1
    )

    resultat.wait_for_publish(timeout=5)

    if not resultat.is_published():
        raise RuntimeError("Publication non confirmee")

    print(f"Mesure {seq} envoyee : {message}", flush=True)

    if seq < 4:
        time.sleep(5)

client.disconnect()
client.loop_stop()

print("Fin du test du capteur.")
