
import json
import paho.mqtt.client as mqtt

BROKER = "10.0.0.7"

TOPIC_DEMANDE = "batiment/acces/demande"
TOPIC_REPONSE = "batiment/acces/reponse"

# Badges autorises pour notre simulation
BADGES_AUTORISES = {"1024", "2048"}


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Serveur d'autorisation connecte !", flush=True)
        client.subscribe(TOPIC_DEMANDE, qos=1)
        print("En attente des demandes d'acces...", flush=True)
    else:
        print(f"Erreur MQTT : {reason_code}", flush=True)


def on_message(client, userdata, msg):

    try:
        demande = json.loads(msg.payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        print("Message invalide recu", flush=True)
        return

    # Lire le numero de badge
    badge = str(demande.get("badge", ""))

    # Verifier la liste des badges autorises
    if badge in BADGES_AUTORISES:
        decision = "ALLOWED"
    else:
        decision = "DENIED"

    # Preparer une reponse associee a la demande
    reponse = {
        "device_id": demande.get("device_id"),
        "seq": demande.get("seq"),
        "decision": decision,
        "request_sent_ns": demande.get("sent_ns")
    }

    # Publier la decision
    client.publish(
        TOPIC_REPONSE,
        json.dumps(reponse),
        qos=1
    )

    print(f"Badge {badge} : {decision}", flush=True)


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="autorisation_serveur"
)

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_forever()
