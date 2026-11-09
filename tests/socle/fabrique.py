"""Fabrique de revues pour les tests du socle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freinet.modele import Revue

T0 = datetime(2026, 1, 1, 7, tzinfo=UTC)


def revue(
    revue_id: str,
    *,
    brainiac_id: str = "b1",
    concept_id: str = "c1",
    nature: str = "rappel",
    note: int = 3,
    jour: float = 0,
    saisi_jour: float | None = None,
    corrige_id: str | None = None,
) -> Revue:
    repondu = T0 + timedelta(days=jour)
    saisi = repondu if saisi_jour is None else T0 + timedelta(days=saisi_jour)
    return Revue(
        revue_id=revue_id,
        brainiac_id=brainiac_id,
        concept_id=concept_id,
        question_id=f"{concept_id}-q-{nature}",
        nature=nature,
        note=note,
        repondu_le=repondu,
        saisi_le=saisi,
        canal="qr",
        corrige_id=corrige_id,
    )
