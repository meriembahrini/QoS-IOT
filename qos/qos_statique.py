#!/usr/bin/env python3

import argparse
import subprocess
import sys

# Interfaces du lien principal Mininet
INTERFACES = {
    "s1-eth7": "src",
    "s2-eth3": "dst",
}

# Classe : identifiant, nom, garantie, priorite, taille file
CLASSES = [
    ("10", "CRITIQUE",  "800kbit", 0, 15),
    ("20", "STREAMING", "5mbit",   1, 45),
    ("30", "DATA",      "4mbit",   2, 30),
    ("40", "DEFAULT",   "200kbit", 3, 10),
]

# Classification des equipements par adresse IP
EQUIPEMENTS = {
    "10.0.0.1": "10",  # alarme
    "10.0.0.2": "10",  # acces
    "10.0.0.3": "30",  # capteur
    "10.0.0.4": "30",  # backup
    "10.0.0.5": "20",  # camera1
    "10.0.0.6": "20",  # camera2
}


def executer(*arguments):
    resultat = subprocess.run(
        arguments,
        capture_output=True,
        text=True
    )

    if resultat.returncode != 0:
        raise RuntimeError(
            f"Commande echouee : {' '.join(arguments)}\n"
            f"{resultat.stderr}"
        )

    return resultat.stdout


def restaurer_interface(interface):
    # Supprimer notre configuration HTB existante
    executer("tc", "qdisc", "del",
             "dev", interface, "root")

    # Reconstituer la configuration originale Mininet
    executer(
        "tc", "qdisc", "add",
        "dev", interface,
        "root", "handle", "5:",
        "htb", "default", "1"
    )

    executer(
        "tc", "class", "add",
        "dev", interface,
        "parent", "5:",
        "classid", "5:1",
        "htb",
        "rate", "10mbit",
        "ceil", "10mbit",
        "burst", "15k",
        "cburst", "1600"
    )

    executer(
        "tc", "qdisc", "add",
        "dev", interface,
        "parent", "5:1",
        "handle", "10:",
        "netem",
        "limit", "100",
        "delay", "5ms"
    )


def installer_interface(interface, sens):
    print(f"\nConfiguration de {interface}...")

    # Remplacer la file unique de Mininet
    executer("tc", "qdisc", "del",
             "dev", interface, "root")

    # Une seule racine HTB limite le lien a 10 Mbit/s
    executer(
        "tc", "qdisc", "add",
        "dev", interface,
        "root", "handle", "5:",
        "htb", "default", "40"
    )

    executer(
        "tc", "class", "add",
        "dev", interface,
        "parent", "5:",
        "classid", "5:1",
        "htb",
        "rate", "10mbit",
        "ceil", "10mbit",
        "burst", "15k",
        "cburst", "1600"
    )

    # Quatre classes partageant la meme capacite
    for identifiant, nom, debit, priorite, limite in CLASSES:

        executer(
            "tc", "class", "add",
            "dev", interface,
            "parent", "5:1",
            "classid", f"5:{identifiant}",
            "htb",
            "rate", debit,
            "ceil", "10mbit",
            "prio", str(priorite),
            "quantum", "1514",
            "burst", "15k",
            "cburst", "1600"
        )

        # Garder un delai simule de 5 ms par sens
        executer(
            "tc", "qdisc", "add",
            "dev", interface,
            "parent", f"5:{identifiant}",
            "handle", f"{identifiant}:",
            "netem",
            "limit", str(limite),
            "delay", "5ms"
        )

        print(f"  {nom:10s} : {debit} - priorite {priorite}")

    # Associer chaque equipement a sa classe
    for ip, classe in EQUIPEMENTS.items():

        executer(
            "tc", "filter", "add",
            "dev", interface,
            "parent", "5:",
            "protocol", "ip",
            "prio", "1",
            "u32",
            "match", "ip", sens, f"{ip}/32",
            "flowid", f"5:{classe}"
        )

    print(f"  Classification IP installee sur {interface}")


def installer():
    # Verifier les interfaces avant de modifier le reseau
    for interface in INTERFACES:
        executer("ip", "link", "show", "dev", interface)

        classes = executer(
            "tc", "class", "show", "dev", interface
        )

        if "class htb 5:1 root" not in classes:
            raise RuntimeError(
                f"{interface} ne possede pas la configuration "
                "Mininet attendue."
            )

        if "class htb 5:10 " in classes:
            raise RuntimeError(
                "QoS statique deja presente. "
                "Executer status ou restore."
            )

    try:
        for interface, sens in INTERFACES.items():
            installer_interface(interface, sens)

    except Exception:
        print(
            "\nErreur : tentative de restauration "
            "de la configuration Mininet.",
            file=sys.stderr
        )

        for interface in INTERFACES:
            try:
                restaurer_interface(interface)
            except Exception as erreur:
                print(erreur, file=sys.stderr)

        raise

    print("\nQoS STATIQUE INSTALLEE !")


def restaurer():
    for interface in INTERFACES:
        executer("ip", "link", "show", "dev", interface)
        restaurer_interface(interface)
        print(f"{interface} : configuration Mininet restauree")

    print("\nRETOUR A LA CONFIGURATION INITIALE !")


def statut():
    for interface in INTERFACES:
        print(f"\n========== {interface} ==========")

        print("\nCLASSES HTB :")
        print(executer(
            "tc", "-s", "class", "show", "dev", interface
        ))

        print("\nFILES RESEAU :")
        print(executer(
            "tc", "-s", "qdisc", "show", "dev", interface
        ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=["apply", "status", "restore"]
    )

    args = parser.parse_args()

    if args.action == "apply":
        installer()
    elif args.action == "status":
        statut()
    elif args.action == "restore":
        restaurer()


if __name__ == "__main__":
    main()
