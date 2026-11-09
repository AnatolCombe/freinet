"""Planification launchd (#53) : trois agents de l'utilisateur, jamais du système.

- `com.freinet.matin` : le rituel à 5 h 57, deux minutes après le réveil de 5 h 55
  (`freinet.matin`) ; launchd le relance au réveil si le Mac dormait, et le rituel est
  idempotent (rattrapage sans doublon) ;
- `com.freinet.heartbeat` : la vérification de 7 h (`freinet.heartbeat`) ;
- `com.freinet.serveur` : la page du QR, toujours en marche.

`python -m freinet.launchd afficher` montre ce qui serait installé ; `installer` écrit les
agents dans `~/Library/LaunchAgents` et les charge ; `desinstaller` les retire. Chaque agent a
un environnement explicite (PATH, langue, chemin de `claude`) : celui de launchd est appauvri.
Le matin et le heartbeat tournent sous `caffeinate -i` : le Mac réveillé par `pmset` ne se
rendort pas pendant le job. La page du QR ne redémarre qu'après un plantage (pas en boucle si
son port est déjà pris). Réveiller le Mac à 5 h 55 demande `sudo` : la commande est affichée,
jamais lancée ici. Un dépôt sous Bureau, Documents ou Téléchargements est protégé par macOS
(TCC) : un agent peut s'y voir refuser l'accès — un avertissement le signale.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
AGENTS = Path.home() / "Library" / "LaunchAgents"
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PMSET = "sudo pmset repeat wakeorpoweron MTWRFSU 05:55:00"
CAFFEINATE = "/usr/bin/caffeinate"
PROTEGES = ("Desktop", "Documents", "Downloads")
ESSAIS_CHARGEMENT = 5
Lanceur = Callable[[list[str]], int]


def agents(
    racine: Path, python: Path, matin: tuple[int, int] = (5, 57), controle: tuple[int, int] = (7, 0)
) -> dict[str, dict[str, object]]:
    """Les agents, sous forme de dictionnaires plist, par label."""
    journal = racine / "data" / "journal"
    environnement = {"PATH": PATH, "LANG": "fr_FR.UTF-8", "PYTHONUNBUFFERED": "1"}
    claude = shutil.which("claude", path=PATH) or shutil.which("claude")
    if claude:
        environnement["FREINET_CLAUDE"] = claude

    def agent(
        label: str, module: str, extra: dict[str, object], eveille: bool = True
    ) -> dict[str, object]:
        nom = label.rsplit(".", 1)[-1]
        commande = [str(python), "-m", module]
        return {
            "Label": label,
            "ProgramArguments": [CAFFEINATE, "-i", *commande] if eveille else commande,
            "WorkingDirectory": str(racine),
            "EnvironmentVariables": dict(environnement),
            "StandardOutPath": str(journal / f"{nom}.log"),
            "StandardErrorPath": str(journal / f"{nom}.log"),
            "ProcessType": "Background",
            **extra,
        }

    return {
        "com.freinet.matin": agent(
            "com.freinet.matin",
            "freinet.matin",
            {"StartCalendarInterval": {"Hour": matin[0], "Minute": matin[1]}},
        ),
        "com.freinet.heartbeat": agent(
            "com.freinet.heartbeat",
            "freinet.heartbeat",
            {"StartCalendarInterval": {"Hour": controle[0], "Minute": controle[1]}},
        ),
        "com.freinet.serveur": agent(
            "com.freinet.serveur",
            "freinet.serveur",
            {"RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 60},
            eveille=False,
        ),
    }


def _launchctl(arguments: list[str]) -> int:
    return subprocess.run(["launchctl", *arguments], capture_output=True).returncode


def avertissements(racine: Path) -> list[str]:
    messages = []
    protege = next((p for p in PROTEGES if (Path.home() / p) in racine.parents), None)
    if protege:
        messages.append(
            f"le dépôt est sous ~/{protege}, protégé par macOS : donner l'accès complet au disque "
            f"à {(racine / '.venv' / 'bin' / 'python').resolve()} (Réglages › Confidentialité), "
            "ou déplacer le dépôt ; puis relire data/journal/*.log après le premier matin"
        )
    if not (shutil.which("claude", path=PATH) or shutil.which("claude")):
        messages.append("commande claude introuvable : le coach utilisera la phrase par défaut")
    return messages


def installer(
    racine: Path,
    python: Path,
    dossier: Path = AGENTS,
    lancer: Lanceur = _launchctl,
    pause: float = 1.0,
) -> list[Path]:
    """Écrit les agents et les (re)charge dans la session graphique de l'utilisateur."""
    (racine / "data" / "journal").mkdir(parents=True, exist_ok=True)
    dossier.mkdir(parents=True, exist_ok=True)
    domaine = f"gui/{os.getuid()}"
    ecrits = []
    for label, contenu in agents(racine, python).items():
        chemin = dossier / f"{label}.plist"
        chemin.write_bytes(plistlib.dumps(contenu))
        lancer(["bootout", f"{domaine}/{label}"])  # absent la première fois : sans effet
        for essai in range(ESSAIS_CHARGEMENT):  # l'agent retiré met parfois un instant à s'arrêter
            if lancer(["bootstrap", domaine, str(chemin)]) == 0:
                break
            time.sleep(pause * (essai + 1))
        else:
            raise OSError(f"launchctl n'a pas chargé {chemin}")
        ecrits.append(chemin)
    return ecrits


def desinstaller(dossier: Path = AGENTS, lancer: Lanceur = _launchctl) -> list[Path]:
    domaine = f"gui/{os.getuid()}"
    retires = []
    for label in agents(RACINE, Path(sys.executable)):
        lancer(["bootout", f"{domaine}/{label}"])
        chemin = dossier / f"{label}.plist"
        if chemin.exists():
            chemin.unlink()
            retires.append(chemin)
    return retires


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("action", choices=["afficher", "installer", "desinstaller"])
    options = lecteur.parse_args(arguments)
    python = RACINE / ".venv" / "bin" / "python"
    for message in avertissements(RACINE):
        print(f"attention : {message}", file=sys.stderr)
    if options.action == "afficher":
        for label, contenu in agents(RACINE, python).items():
            print(f"--- {label}.plist")
            print(plistlib.dumps(contenu).decode("utf-8"))
    elif options.action == "installer":
        try:
            for chemin in installer(RACINE, python):
                print(f"installé : {chemin}")
        except OSError as erreur:
            print(f"installation impossible : {erreur}", file=sys.stderr)
            return 1
    else:
        for chemin in desinstaller():
            print(f"retiré : {chemin}")
    print(f"\nPour réveiller le Mac chaque matin (à lancer soi-même) :\n  {PMSET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
