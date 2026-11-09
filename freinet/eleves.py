"""Gérer les BRAINIACs : `ajouter <nom> <fuseau>` et `inscrire <nom> <carte> [--quete id]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from freinet.base import Base, ErreurSQLite
from freinet.bibliotheque import Bibliotheque, charger
from freinet.contenu import IDENTIFIANT

RACINE = Path(__file__).resolve().parent.parent


class Refus(ValueError):
    """Demande invalide : message d'une ligne, code 1, rien n'est écrit."""


def _ajouter(racine: Path, nom: str, fuseau: str) -> str:
    if not IDENTIFIANT.match(nom):
        # Le nom devient un dossier (`brainiacs/<nom>/`) : jamais de `/` ni de `..`.
        raise Refus(f"nom invalide : {nom} (minuscules, chiffres, tirets)")
    try:
        ZoneInfo(fuseau)
    except (ZoneInfoNotFoundError, ValueError):
        raise Refus(f"fuseau inconnu : {fuseau}") from None
    with Base(racine / "data" / "freinet.db") as base:
        if base.brainiac_par_nom(nom) is not None:
            raise Refus(f"élève déjà existant : {nom}")
        return base.ajouter_brainiac(nom, fuseau)


def valider_inscription(bib: Bibliotheque, carte: str, quete: str | None) -> None:
    """Refuse une carte non publiée ou une quête d'une autre carte (commande et API ADVIZA)."""
    if carte not in bib.cartes:
        raise Refus(f"carte inconnue : {carte}")
    if quete is not None:
        if quete not in bib.quetes:
            raise Refus(f"quête inconnue : {quete}")
        if bib.quetes[quete].carte != carte:
            raise Refus(f"la quête {quete} appartient à la carte {bib.quetes[quete].carte}")


def _inscrire(racine: Path, nom: str, carte: str, quete: str | None) -> None:
    valider_inscription(charger(racine / "bibliotheque"), carte, quete)
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom(nom)
        if eleve is None:
            raise Refus(f"élève inconnu : {nom}")
        base.inscrire(eleve.brainiac_id, carte, quete)


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--racine", type=Path, default=RACINE)
    actions = lecteur.add_subparsers(dest="action", required=True)
    ajouter = actions.add_parser("ajouter")
    ajouter.add_argument("nom")
    ajouter.add_argument("fuseau", help="fuseau IANA, ex. Europe/Paris")
    inscrire = actions.add_parser("inscrire")
    inscrire.add_argument("nom")
    inscrire.add_argument("carte")
    inscrire.add_argument("--quete")
    options = lecteur.parse_args(arguments)
    try:
        if options.action == "ajouter":
            print(_ajouter(options.racine, options.nom, options.fuseau))
        else:
            _inscrire(options.racine, options.nom, options.carte, options.quete)
    except (ValueError, OSError, ErreurSQLite) as erreur:
        # Refus, bibliothèque illisible (ErreurContenu), disque, base verrouillée : une ligne.
        print(erreur, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
