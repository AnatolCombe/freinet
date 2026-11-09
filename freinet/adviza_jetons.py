"""Les jetons de l'API ADVIZA (PROF-A) : `_config/adviza.md`, un jeton par compte ADVIZA.

Chaque jeton ouvre un seul élève (`brainiac_id`) : deux élèves restent cloisonnés.
Le fichier ne garde que l'empreinte SHA-256 du jeton (256 bits aléatoires : rien à deviner) ;
le clair n'est affiché qu'une fois (`python -m freinet.adviza_jetons nouveau <élève>`), puis
recopié dans ADVIZA. Révoquer = retirer la ligne, relancer la page du QR. Jamais journalisé.
La table des jetons reste en fin de fichier : la commande y ajoute sa ligne.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

from freinet.base import Base, ErreurSQLite

RACINE = Path(__file__).resolve().parent.parent
FICHIER_ADVIZA = RACINE / "_config" / "adviza.md"
PORT_PAR_DEFAUT = 8766
_PORT = re.compile(r"^\|\s*Port\s*\|\s*(\d{1,6})\s*\|\s*$", re.MULTILINE)
_JETON = re.compile(r"^\|\s*([0-9a-f-]{36})\s*\|\s*([0-9a-f]{64})\s*\|\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ConfigAdviza:
    port: int
    jetons: dict[str, str]  # empreinte → brainiac_id

    def eleve(self, jeton: str) -> str | None:
        """Le `brainiac_id` du jeton, sinon `None` ; toutes les empreintes sont comparées à
        temps constant : la durée ne dit rien du jeton présenté."""
        cherche, trouve = empreinte(jeton), None
        for connue, brainiac_id in self.jetons.items():
            if hmac.compare_digest(connue, cherche):
                trouve = brainiac_id
        return trouve if jeton else None


def empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def lire_config_adviza(chemin: Path | None = None) -> ConfigAdviza:
    chemin = chemin or FICHIER_ADVIZA
    texte = chemin.read_text(encoding="utf-8")
    trouve = _PORT.search(texte)
    port = int(trouve.group(1)) if trouve else PORT_PAR_DEFAUT
    if not 0 < port < 65536:
        raise ValueError(f"port invalide dans {chemin} : {port}")
    jetons: dict[str, str] = {}
    for brainiac_id, hache in _JETON.findall(texte):
        if hache in jetons:
            raise ValueError(f"empreinte en double dans {chemin}")
        jetons[hache] = brainiac_id
    return ConfigAdviza(port, jetons)


def nouveau_jeton(racine: Path, nom: str, chemin: Path | None = None) -> str:
    """Un jeton neuf pour cet élève : son empreinte s'ajoute à la table, le clair est rendu."""
    chemin = chemin or FICHIER_ADVIZA
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom(nom)
    if eleve is None:
        raise ValueError(f"élève inconnu : {nom}")
    jeton = secrets.token_urlsafe(32)
    debut = "" if chemin.read_text(encoding="utf-8").endswith("\n") else "\n"
    with chemin.open("a", encoding="utf-8") as fichier:
        fichier.write(f"{debut}| {eleve.brainiac_id} | {empreinte(jeton)} |\n")
    return jeton


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--racine", type=Path, default=RACINE)
    lecteur.add_argument("--config", type=Path, default=None, help="défaut : _config/adviza.md")
    lecteur.add_subparsers(dest="action", required=True).add_parser("nouveau").add_argument("nom")
    options = lecteur.parse_args(arguments)
    try:
        jeton = nouveau_jeton(options.racine, options.nom, options.config)
    except (ValueError, OSError, ErreurSQLite) as erreur:
        print(erreur, file=sys.stderr)
        return 1
    print(f"{jeton}\n↑ à recopier dans ADVIZA ; il ne sera plus affiché. Relancer la page du QR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
