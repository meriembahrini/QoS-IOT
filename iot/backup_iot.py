
import argparse
import subprocess
import time
from pathlib import Path

SERVEUR_IPERF = "10.0.0.7"
PORT = 5304

parser = argparse.ArgumentParser()
parser.add_argument("--cycles", type=int, default=3)
parser.add_argument("--duration", type=int, default=8)
parser.add_argument("--pause", type=int, default=5)
parser.add_argument("--rate", default="5M")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "results" / "backup"
DOSSIER.mkdir(parents=True, exist_ok=True)

FICHIER = DOSSIER / "backup_periodique.log"

for numero in range(1, args.cycles + 1):

    print(f"\n===== SAUVEGARDE {numero} =====", flush=True)
    print(f"Debit cible : {args.rate}", flush=True)

    commande = [
        "iperf3",
        "-c", SERVEUR_IPERF,
        "-p", str(PORT),
        "-b", args.rate,
        "-t", str(args.duration),
        "-i", "1"
    ]

    with open(FICHIER, "a") as log:
        log.write(f"\n===== SAUVEGARDE {numero} =====\n")
        log.flush()

        resultat = subprocess.run(
            commande,
            stdout=log,
            stderr=subprocess.STDOUT
        )

    if resultat.returncode != 0:
        raise RuntimeError(
            f"Echec de la sauvegarde {numero}. "
            f"Consulter {FICHIER}"
        )

    print(f"Sauvegarde {numero} terminee", flush=True)

    if numero < args.cycles:
        print(f"Pause de {args.pause} secondes", flush=True)
        time.sleep(args.pause)

print("\nToutes les sauvegardes sont terminees.")
