"""Recalcule l'état d'un élève depuis son journal et l'écrit dans les caches (inv. 4)."""

from __future__ import annotations

from collections.abc import Callable

from freinet.base import Base
from freinet.constantes import ReglesAcquis
from freinet.modele import EtatConcept
from freinet.rejeu import rejouer


def recalculer(
    base: Base,
    brainiac_id: str,
    regles: ReglesAcquis,
    canonique: Callable[[str], str] | None = None,
) -> list[EtatConcept]:
    """Rejoue le journal et remplace les caches, lecture et écriture sous le même verrou."""
    return base.remplacer_etat(brainiac_id, lambda revues: rejouer(revues, regles, canonique))


def etat_coherent(
    base: Base,
    brainiac_id: str,
    regles: ReglesAcquis,
    canonique: Callable[[str], str] | None = None,
) -> bool:
    """Vrai si les caches de la base sont exactement ce que redonne le rejeu du journal."""
    return base.etat(brainiac_id) == rejouer(base.revues(brainiac_id), regles, canonique)
