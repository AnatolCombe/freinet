"""Heartbeat (#44), lancé par launchd vers 7 h : chaque élève a-t-il reçu son ticket ? Le
papier tiendra-t-il ? La page du QR répond-elle ?

`python -m freinet.heartbeat` : sans rien à signaler, code 0 et silence. Sinon une
notification macOS par alerte (sans rien de secret : ni jeton, ni contenu du ticket), le même
texte sur la sortie d'erreur, et le code 1. Il attend d'abord que le rituel du matin ait fini
(même verrou) : un Mac réveillé tard lance les deux ensemble, sans fausse alerte.
`--essai` envoie une notification de test (mise en service : autoriser les notifications).
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from freinet.acces import lire_config_retour
from freinet.base import Base, ErreurSQLite
from freinet.imprimante import Cible, etat_papier, lire_imprimante
from freinet.temps import date_logique, depuis_iso, maintenant
from freinet.verrou import verrou_du_rituel

RACINE = Path(__file__).resolve().parent.parent
TITRE = "FREINET"
ATTENTE_RITUEL_S = 300.0


def alertes(racine: Path, instant: datetime, cible: Cible | None) -> list[str]:
    messages: list[str] = []
    base_chemin = racine / "data" / "freinet.db"
    if not base_chemin.is_file():
        return [f"base absente : {base_chemin}"]
    with Base(base_chemin) as base:
        eleves = [base.brainiac(b) for b in base.brainiacs()]
        if not eleves:
            messages.append("aucun élève (python -m freinet.eleves ajouter …)")
        for eleve in sorted((e for e in eleves if e is not None), key=lambda e: e.nom):
            jour = date_logique(instant, eleve.fuseau)
            statut = base.statut_du_plan(eleve.brainiac_id, jour)
            if statut not in ("imprime", "note"):
                cause = "plan prêt, non imprimé" if statut else "aucun plan"
                messages.append(f"{eleve.nom} : pas de ticket le {jour.isoformat()} ({cause})")
    if cible is not None:
        try:
            papier = etat_papier(cible)
        except OSError as erreur:
            messages.append(f"imprimante injoignable ({erreur or type(erreur).__name__})")
        else:
            if papier != "ok":
                messages.append(f"papier : {papier}")
    return messages


def page_injoignable(port: int, ecoute: str = "0.0.0.0", delai: float = 3.0) -> str | None:
    """La page du QR (servie par l'agent `com.freinet.serveur`) accepte-t-elle une connexion ?"""
    hote = "127.0.0.1" if ecoute in ("0.0.0.0", "") else ecoute
    try:
        with socket.create_connection((hote, port), timeout=delai):
            return None
    except OSError as erreur:
        return f"page du QR injoignable sur le port {port} ({erreur or type(erreur).__name__})"


def notifier(message: str) -> bool:
    """Notification macOS ; le texte passe en argument, jamais dans le script (pas d'injection),
    et commence par un préfixe fixe (osascript lirait un argument « -e … » comme du script)."""
    osascript = shutil.which("osascript")
    if osascript is None:
        return False
    afficher = f'display notification (item 1 of argv) with title "{TITRE}"'
    script = ["-e", "on run argv", "-e", afficher, "-e", "end run"]
    try:
        fait = subprocess.run([osascript, *script, f"• {message}"], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return fait.returncode == 0


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--racine", type=Path, default=RACINE)
    lecteur.add_argument("--instant", type=depuis_iso, help="instant ISO 8601 (tests)")
    lecteur.add_argument("--sans-imprimante", action="store_true", help="ne pas sonder le papier")
    lecteur.add_argument("--sans-page", action="store_true", help="ne pas sonder la page du QR")
    lecteur.add_argument("--essai", action="store_true", help="envoyer une notification de test")
    options = lecteur.parse_args(arguments)
    if options.essai:
        envoyee = notifier("essai : les alertes du heartbeat arrivent bien")
        print("notification envoyée" if envoyee else "notification refusée (osascript)")
        return 0 if envoyee else 1
    cible = None
    if not options.sans_imprimante:
        try:
            cible = lire_imprimante()
        except (ValueError, OSError):
            cible = None  # pas encore configurée : seul le ticket est vérifié
    try:
        with verrou_du_rituel(options.racine, ATTENTE_RITUEL_S):  # le matin a fini
            messages = alertes(options.racine, options.instant or maintenant(), cible)
        if not options.sans_page:
            config = lire_config_retour()
            injoignable = page_injoignable(config.port, config.ecoute)
            messages += [injoignable] if injoignable else []
    except (ValueError, OSError, ErreurSQLite) as erreur:
        messages = [f"heartbeat impossible : {erreur}"]
    for message in messages:
        print(message, file=sys.stderr)
        if not notifier(message):
            print("(notification non envoyée)", file=sys.stderr)
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(main())
