"""FSRS délégué à py-fsrs (#1). Une carte FSRS par élève × concept (A8).

Fuzzing coupé et pas de pas d'apprentissage en minutes : le ticket est quotidien,
et deux rejeux du même journal doivent donner exactement les mêmes échéances (inv. 4).
Les instants sont convertis en UTC ici : fsrs refuse tout autre fuseau.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fsrs import Card, Rating, Scheduler

_PLANIFICATEUR = Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)


def carte_neuve(premiere_revue: datetime) -> Card:
    """Carte d'un concept jamais révisé. `card_id` fixe : l'identité est (élève, concept)."""
    return Card(card_id=0, due=premiere_revue.astimezone(UTC))


def reviser(carte: Card, note: int, quand: datetime) -> Card:
    nouvelle, _journal = _PLANIFICATEUR.review_card(
        carte, Rating(note), review_datetime=quand.astimezone(UTC)
    )
    return nouvelle


def retention(carte: Card, quand: datetime) -> float:
    """Probabilité de rappel prévue à l'instant `quand`, sans nouvelle révision."""
    return float(
        _PLANIFICATEUR.get_card_retrievability(carte, current_datetime=quand.astimezone(UTC))
    )


def vers_json(carte: Card) -> str:
    return json.dumps(carte.to_dict(), sort_keys=True)


def depuis_json(texte: str) -> Card:
    return Card.from_dict(json.loads(texte))
