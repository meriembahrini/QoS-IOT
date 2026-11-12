
import json
import time
from threading import Event
import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"
TOPIC = "batiment/alarme"

# Indique si la connexion MQTT est etablie
connecte = Event()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Alarme connectee au broker MQTT !", flush=True)
        connecte.set()
    else:
        print(f"Erreur de connexion : {reason_code}", flush=True)


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="alarme_01"
)

client.on_connect = on_connect

# Demarrer la connexion MQTT
client.connect(BROKER, 1883, 60)
client.loop_start()

if not connecte.wait(timeout=5):
    raise RuntimeError("Connexion MQTT non etablie")

# Envoyer 5 messages
for seq in range(1, 6):

    evenement = "HEARTBEAT"

    if seq == 5:
        evenement = "FIRE_DETECTED"

    message = {
        "device_id": "alarme_01",
        "seq": seq,
        "event": evenement,
        "sent_ns": time.time_ns()
    }

    resultat = client.publish(
        TOPIC,
        json.dumps(message),
        qos=1
    )

    resultat.wait_for_publish(timeout=5)

    if not resultat.is_published():
        raise RuntimeError(f"Publication {seq} non confirmee")

    print(f"Message {seq} publie : {evenement}", flush=True)

    time.sleep(1)

client.disconnect()
client.loop_stop()

print("Fin du test MQTT.")
