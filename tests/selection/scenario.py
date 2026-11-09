"""Scénarios de sélection sur la carte de démonstration (harmonie-demo)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freinet.bibliotheque import charger
from freinet.constantes import lire_regles
from freinet.dose import lire_dose
from freinet.langue import FR, Libelles
from freinet.modele import Inscription, Revue
from freinet.rejeu import rejouer
from freinet.selection import Selection, selectionner
from tests.bibliotheque.demo import DEMO

BIB = charger(DEMO)
REGLES = lire_regles()
DOSE = lire_dose()
LUNDI = datetime(2026, 1, 5, 5, 0, tzinfo=UTC)  # 6 h à Paris
INSCRIPTION = [Inscription("harmonie-demo", "entendre-une-cadence")]
DECLARES = (0, 100, 0)


def reponse(n: int, question_id: str, note: int, jour: float) -> Revue:
    question = BIB.questions[question_id]
    instant = LUNDI + timedelta(days=jour)
    return Revue(
        f"r{n:03d}",
        "b1",
        question.concept,
        question_id,
        question.nature,
        note,
        instant,
        instant,
        "qr",
    )


def selection(
    revues: list[Revue],
    jour: float = 0,
    dosage: tuple[int, int, int] = DECLARES,
    libelles: Libelles = FR,
) -> Selection:
    return selectionner(
        BIB,
        rejouer(revues, REGLES, BIB.canonique),
        revues,
        INSCRIPTION,
        "b1",
        "Europe/Paris",
        dosage,
        DOSE,
        LUNDI + timedelta(days=jour),
        libelles=libelles,
    )
