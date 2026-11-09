"""Objets échangés entre la base, le rejeu et le reste du moteur. Aucune I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

NATURES = ("rappel", "application", "transfert", "piege", "amorce_feynman", "pre_test")


@dataclass(frozen=True)
class Revue:
    """Une ligne du journal `revue` : la seule vérité (inv. 3, inv. 4)."""

    revue_id: str
    brainiac_id: str
    concept_id: str
    question_id: str
    nature: str
    note: int
    repondu_le: datetime
    saisi_le: datetime
    canal: str
    plan_id: str | None = None
    corrige_id: str | None = None

    def __post_init__(self) -> None:
        if self.nature not in NATURES:
            raise ValueError(f"nature inconnue : {self.nature!r}")
        if not 1 <= self.note <= 4:
            raise ValueError(f"note hors de 1-4 : {self.note}")
        if self.repondu_le.tzinfo is None or self.saisi_le.tzinfo is None:
            raise ValueError("horodatages sans fuseau")


@dataclass(frozen=True)
class Brainiac:
    brainiac_id: str
    nom: str
    fuseau: str
    dosage: tuple[int, int, int]  # projets / déclarés / sérendipité (B5)


@dataclass(frozen=True)
class Inscription:
    carte_id: str
    quete_active: str | None


@dataclass(frozen=True)
class EtatConcept:
    """L'état recalculé d'un concept pour un élève : cache de `fsrs` + `maitrise`."""

    brainiac_id: str
    concept_id: str
    carte_json: str
    nb_revues: int
    acquis_le: datetime | None

    @property
    def etat(self) -> str:
        return "acquis" if self.acquis_le is not None else "en_cours"
