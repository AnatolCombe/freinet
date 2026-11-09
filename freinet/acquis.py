"""Règle « acquis » (inv. 5, A7) — fonction pure, sans I/O ni LLM."""

from __future__ import annotations

from datetime import timedelta

from fsrs import Card

from freinet.constantes import ReglesAcquis
from freinet.planification import retention


def regle_satisfaite(carte: Card, transferts_reussis: int, regles: ReglesAcquis) -> bool:
    """Vrai si le concept tient encore `horizon_jours` sans révision ET si le transfert est prouvé.

    L'horizon part de la dernière revue de la carte : juste après une revue, la rétention
    « maintenant » vaut ~1, c'est donc la rétention prévue à l'horizon qui mesure une
    mémoire durable. Une carte jamais révisée n'est jamais acquise.
    """
    if transferts_reussis < regles.transferts_requis or carte.last_review is None:
        return False
    horizon = carte.last_review + timedelta(days=regles.horizon_jours)
    return retention(carte, horizon) >= regles.retention
