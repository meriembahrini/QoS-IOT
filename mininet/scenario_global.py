
import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(ROOT / ".venv/bin/python")

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULTATS = ROOT / "results/scenarios" / RUN_ID
RESULTATS.mkdir(parents=True, exist_ok=True)

CSV_IOT = ROOT / "results/mqtt/evenements_iot.csv"

processus = []
fichiers = []


def actif(nom_script):
    lignes = net["serveur"].cmd("ps -eo args").splitlines()
    return any(
        f"/iot/{nom_script}" in ligne
        and "python" in ligne
        for ligne in lignes
    )


def lancer(hote, commande, nom_log):
    chemin = RESULTATS / f"{nom_log}.log"
    fichier = open(chemin, "w", encoding="utf-8")
    fichiers.append(fichier)

    proc = net[hote].popen(
        commande,
        stdout=fichier,
        stderr=subprocess.STDOUT
    )

    processus.append(proc)
    return proc


def application(hote, script, etiquette):
    return lancer(
        hote,
        [PYTHON, "-u", str(ROOT / "iot" / script)],
        etiquette
    )


def publier(evenement):
    message = json.dumps({
        "device_id": "alarme_01",
        "event": evenement
    })

    proc = net["alarme"].popen([
        "mosquitto_pub",
        "-h", "10.0.0.7",
        "-t", "batiment/securite/evenements",
        "-m", message,
        "-q", "1"
    ])

    if proc.wait(timeout=10) != 0:
        raise RuntimeError("Publication MQTT echouee")

    print(f"EVENEMENT : {evenement}", flush=True)


def mesurer_reseau(phase):
    for lien in net.links:
        noms = {lien.intf1.node.name, lien.intf2.node.name}

        if noms == {"s1", "s2"}:
            for interface in (lien.intf1, lien.intf2):
                sortie = interface.node.cmd(
                    f"tc -s qdisc show dev {interface.name}"
                )

                chemin = RESULTATS / (
                    f"{phase}_{interface.name}_tc.txt"
                )
                chemin.write_text(sortie)
            return

    print("Attention : lien s1-s2 non trouve")


def phase(nom, duree, sauvegarde=False):
    print(f"\n===== PHASE {nom.upper()} =====", flush=True)

    debut = datetime.now(timezone.utc).isoformat()

    application("capteur", "capteur_mqtt.py", f"{nom}_capteur")
    application("acces", "acces_mqtt.py", f"{nom}_acces")

    lancer(
        "alarme",
        [
            "ping", "-n",
            "-i", "0.5",
            "-c", "20",
            "-W", "1",
            "10.0.0.7"
        ],
        f"{nom}_ping"
    )

    if sauvegarde:
        lancer(
            "backup",
            [
                PYTHON, "-u",
                str(ROOT / "iot/backup_iot.py"),
                "--cycles=3",
                "--duration=8",
                "--pause=5",
                "--rate=5M"
            ],
            "backup"
        )

    time.sleep(duree)
    mesurer_reseau(nom)

    fin = datetime.now(timezone.utc).isoformat()
    return [nom, debut, fin]


def scenario():
    print(f"Resultats : {RESULTATS}", flush=True)

    serveur = net["serveur"]
    ports = serveur.cmd("ss -lnt")

    if ":1883" not in ports:
        raise RuntimeError("Broker MQTT non demarre")

    for port in (5302, 5303, 5304):
        if f":{port}" not in ports:
            lancer(
                "serveur",
                ["iperf3", "-s", "-p", str(port)],
                f"serveur_iperf_{port}"
            )

    # Eviter deux simulateurs sur une meme camera
    if actif("camera_iot.py"):
        raise RuntimeError(
            "Un ancien camera_iot.py fonctionne encore. "
            "Terminer les anciennes simulations avant ce test."
        )

    if not actif("supervision_iot.py"):
        application(
            "monitor",
            "supervision_iot.py",
            "supervision"
        )

    if not actif("autorisation_mqtt.py"):
        application(
            "serveur",
            "autorisation_mqtt.py",
            "autorisation"
        )

    time.sleep(2)

    # Memoriser la position actuelle du CSV
    position_csv = CSV_IOT.stat().st_size if CSV_IOT.exists() else 0

    for camera in ("camera1", "camera2"):
        lancer(
            camera,
            [
                PYTHON, "-u",
                str(ROOT / "iot/camera_iot.py"),
                f"--camera={camera}",
                "--duree=150"
            ],
            camera
        )
    # Laisser le temps aux cameras de s'abonner
        time.sleep(3)

    # Alarme MQTT continue pendant tout le scenario
    lancer(
        "alarme",
        [
                PYTHON, "-u",
                str(ROOT / "iot/alarme_continue.py"),
                "--duree=110",
                "--intervalle=1"
        ],
        "alarme_continue"
    )

    phases = []
    phases.append(phase("normal", 24))

    publier("INTRUSION_DETECTED")
    phases.append(phase("congestion", 38, sauvegarde=True))

    publier("RETURN_TO_NORMAL")
    phases.append(phase("recuperation", 24))

    with open(RESULTATS / "phases.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["phase", "debut_utc", "fin_utc"])
        writer.writerows(phases)
    # Conserver uniquement les nouveaux messages MQTT
    if CSV_IOT.exists():
        with open(CSV_IOT, "rb") as source:
            source.seek(position_csv)
            nouvelles_lignes = source.read()

        with open(RESULTATS / "evenements_iot.csv", "wb") as dest:
            dest.write(
                b"date_reception,topic,device_id,seq,event,"
                b"temperature,humidity,badge,decision,delai_ms\n"
            )
            dest.write(nouvelles_lignes)

    print("\n===== SCENARIO TERMINE =====")
    print("Resultats :", RESULTATS, flush=True)


try:
    scenario()

finally:
    for proc in processus:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    for fichier in fichiers:
        fichier.close()
