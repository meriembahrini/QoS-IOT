"""Test de surcharge IoT : 2 cameras UDP, backup TCP, alarme ICMP.

A lancer depuis la console Mininet, en lui transmettant l'objet `net` :
px __import__('runpy').run_path('/CHEMIN/mininet/test_limites_qos.py', init_globals={'net': net})

La QoS n'est PAS modifiee par ce script.
"""

from datetime import datetime
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
RESULTATS = ROOT / 'results' / 'tests_limites_qos' / datetime.now().strftime('%Y%m%d_%H%M%S')
RESULTATS.mkdir(parents=True, exist_ok=True)

SERVEUR = '10.0.0.7'
DUREE = 30
FLUX = {
    'camera1': ['iperf3', '-c', SERVEUR, '-p', '5302', '-u', '-b', '6M', '-l', '1200', '-t', str(DUREE), '-i', '1'],
    'camera2': ['iperf3', '-c', SERVEUR, '-p', '5303', '-u', '-b', '6M', '-l', '1200', '-t', str(DUREE), '-i', '1'],
    'backup':  ['iperf3', '-c', SERVEUR, '-p', '5304', '-b', '5M', '-t', str(DUREE), '-i', '1'],
}


def etat_qos():
    try:
        aller = subprocess.check_output(['tc', 'class', 'show', 'dev', 's1-eth7'], text=True)
        retour = subprocess.check_output(['tc', 'class', 'show', 'dev', 's2-eth3'], text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError('Le lien Mininet s1-eth7 / s2-eth3 est introuvable.') from e
    if 'class htb 5:10 parent 5:1' in aller and 'class htb 5:10 parent 5:1' in retour:
        return 'QOS STATIQUE HTB'
    if 'class htb 5:1 root leaf' in aller and 'class htb 5:1 root leaf' in retour:
        return 'SANS QOS DIFFERENCIEE'
    return 'CONFIGURATION RESEAU A VERIFIER'
def resume_iperf(nom):
    lignes = (RESULTATS / f'{nom}.log').read_text(errors='replace').splitlines()
    recep = [s.strip() for s in lignes if re.search(r'\breceiver\s*$', s)]
    envoi = [s.strip() for s in lignes if re.search(r'\bsender\s*$', s)]
    if not recep:
        return f'{nom}: aucune statistique receiver ; verifier {nom}.log'
    resultat = f'{nom} (recu) : {recep[-1]}'
    if nom == 'backup' and envoi:
        resultat += f'\n  backup (emis) : {envoi[-1]}'
    return resultat


def executer_test():
    mode = etat_qos()
    print('\n===== TEST DE SURCHARGE IoT =====', flush=True)
    print('Configuration :', mode, flush=True)
    print('2 cameras UDP x 6 Mbit/s + backup TCP cible 5 Mbit/s', flush=True)
    print('Lien s1-s2 : 10 Mbit/s', flush=True)
    print('Resultats :', RESULTATS, flush=True)

    # Les trois serveurs iperf3 doivent ecouter avant l'experience.
    ports = net['serveur'].cmd('ss -lnt')
    absents = [str(p) for p in (5302, 5303, 5304) if not re.search(rf':{p}\b', ports)]
    if absents:
        raise RuntimeError('Serveurs iperf3 absents sur les ports : ' + ', '.join(absents))

    # Refuser les tests si d'anciennes cameras autonomes sont actives.
    ps = subprocess.check_output(['ps', '-eo', 'args'], text=True)
    if any('camera_iot.py' in ligne and ('python' in ligne) for ligne in ps.splitlines()):
        raise RuntimeError('Un programme camera_iot.py fonctionne encore. Arrete-le avant le test.')

    handles = []
    processus = {}
    try:
        # Demarrer rapidement les trois generateurs pour une surcharge simultanee.
        for nom, commande in FLUX.items():
            fichier = open(RESULTATS / f'{nom}.log', 'w', encoding='utf-8')
            handles.append(fichier)
            processus[nom] = net[nom].popen(
                commande, stdout=fichier, stderr=subprocess.STDOUT
            )
            print(f'[DEMARRAGE] {nom}', flush=True)

        time.sleep(3)
        print('[MESURE] Ping de l\'alarme pendant la surcharge...', flush=True)
        with open(RESULTATS / 'alarme_ping.log', 'w', encoding='utf-8') as f:
            ping = net['alarme'].popen(
                ['ping', '-n', '-c', '15', '-i', '0.5', '-W', '1', SERVEUR],
                stdout=f, stderr=subprocess.STDOUT
            )
            ping.wait(timeout=25)

        for nom, proc in processus.items():
            if proc.wait(timeout=DUREE + 15) != 0:
                print(f'[ATTENTION] {nom} : erreur iperf3, voir le log', flush=True)
    finally:
        for proc in processus.values():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        for f in handles:
            f.close()

    ping_lignes = (RESULTATS / 'alarme_ping.log').read_text(errors='replace').splitlines()
    ping_resume = [s for s in ping_lignes if 'packet loss' in s or 'rtt min/avg' in s]
    texte = [f'CONFIGURATION : {mode}', '', 'ALARME (ICMP)']
    texte.extend(ping_resume or ['Pas de bilan ping ; voir alarme_ping.log'])
    texte.extend(['', 'DEBITS ET PERTES (iperf3)'])
    for nom in ('camera1', 'camera2', 'backup'):
        texte.append(resume_iperf(nom))
    texte.extend(['', f'Logs complets : {RESULTATS}'])
    compte_rendu = '\n'.join(texte) + '\n'
    (RESULTATS / 'resume.txt').write_text(compte_rendu, encoding='utf-8')
    print('\n===== RESULTATS DU TEST =====\n' + compte_rendu, flush=True)


# Le script est execute par runpy.run_path depuis la console Mininet.
if 'net' not in globals():
    raise RuntimeError('Lancer ce fichier depuis Mininet en fournissant la variable net.')

executer_test()
