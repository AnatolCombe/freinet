"""Sauvegarde cohérente et restauration vérifiée (#3).

`revue` n'existe que dans la base : c'est la seule donnée que rien ne peut régénérer.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from freinet.base import Base, ErreurSQLite
from freinet.constantes import ReglesAcquis
from freinet.etat import etat_coherent


class ErreurSauvegarde(RuntimeError):
    pass


def nom_sauvegarde(quand: datetime) -> str:
    if quand.tzinfo is None:
        raise ValueError(f"instant sans fuseau : {quand!r}")
    return f"freinet-{quand.astimezone(UTC):%Y%m%dT%H%M%SZ}.db"


def sauvegarder(base: Base, dossier: Path, quand: datetime) -> Path:
    """Vérifie l'intégrité, copie la base par VACUUM INTO dans un fichier temporaire, puis le
    publie sous son nom définitif d'un seul geste : jamais d'écrasement, jamais de copie
    tronquée sous le nom final (disque plein, coupure)."""
    if not base.integre():
        raise ErreurSauvegarde("integrity_check en échec : pas de sauvegarde d'une base corrompue")
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / nom_sauvegarde(quand)
    if cible.exists():
        raise ErreurSauvegarde(f"{cible} existe déjà")
    partiel = cible.with_suffix(".db.partiel")
    partiel.unlink(missing_ok=True)
    try:
        base.copier_vers(partiel)
        os.link(partiel, cible)  # échoue si la cible est apparue entre-temps
    except FileExistsError:
        raise ErreurSauvegarde(f"{cible} existe déjà") from None
    except ErreurSQLite as erreur:
        raise ErreurSauvegarde(f"copie impossible : {erreur}") from erreur
    finally:
        partiel.unlink(missing_ok=True)
    return cible


def restauration_valide(
    chemin: Path, regles: ReglesAcquis, canonique: Callable[[str], str] | None = None
) -> bool:
    """Vrai si la sauvegarde s'ouvre, est intègre, contient au moins un élève et si chaque
    élève se rejoue à l'identique. La vérification porte sur une copie jetable : la
    sauvegarde elle-même n'est jamais modifiée (ni passage en WAL, ni migration)."""
    if not chemin.is_file():
        return False
    with tempfile.TemporaryDirectory() as dossier:
        essai = Path(dossier) / chemin.name
        shutil.copyfile(chemin, essai)
        try:
            with Base(essai) as copie:
                eleves = copie.brainiacs()
                return (
                    copie.integre()
                    and bool(eleves)
                    and all(etat_coherent(copie, b, regles, canonique) for b in eleves)
                )
        except ErreurSQLite:
            return False
