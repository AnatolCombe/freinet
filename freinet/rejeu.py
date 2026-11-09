"""Rejeu du journal `revue` → état FSRS et maîtrise (inv. 4, #17). Pur : aucune I/O.

Ordre total : (repondu_le, revue_id). L'heure de saisie ne compte pas — FSRS dépend du
délai réel entre deux réponses, pas de l'heure du scan.

« Acquis ne recule jamais » (A7) vaut pour le journal tel qu'il s'allonge dans le temps : une
fois acquis, aucune revue ultérieure ne le retire. Une correction de note ou une réponse
saisie en retard (datée avant l'acquisition) réécrit l'histoire : le rejeu en tient compte
et peut alors dater l'acquisition autrement, ou pas du tout.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime

from fsrs import Card

from freinet.acquis import regle_satisfaite
from freinet.constantes import ReglesAcquis
from freinet.modele import EtatConcept, Revue
from freinet.planification import carte_neuve, reviser, vers_json

NOTE_REUSSIE = 3


@dataclass
class _Cumul:
    carte: Card
    nb_revues: int = 0
    transferts_reussis: int = 0
    acquis_le: datetime | None = None


def _origine(revue: Revue, par_id: dict[str, Revue]) -> str:
    """Remonte une chaîne de corrections jusqu'à la revue d'origine."""
    vues = {revue.revue_id}
    while revue.corrige_id is not None and revue.corrige_id in par_id:
        revue = par_id[revue.corrige_id]
        if revue.revue_id in vues:
            raise ValueError(f"cycle de corrections autour de {revue.revue_id}")
        vues.add(revue.revue_id)
    return revue.revue_id


def effectives(revues: Iterable[Revue]) -> list[Revue]:
    """Applique les corrections puis ordonne totalement.

    Une correction est une revue dont `corrige_id` pointe vers la revue corrigée (d'origine
    ou elle-même une correction) : seule sa note compte, elle remplace celle de la revue
    d'origine (la dernière saisie de la chaîne l'emporte) sans toucher à son horodatage ni à
    sa nature. Une correction dont l'origine est absente de la liste est ignorée.
    """
    toutes = list(revues)
    par_id = {r.revue_id: r for r in toutes}
    corrections: dict[str, Revue] = {}
    for r in sorted(toutes, key=lambda r: (r.saisi_le, r.revue_id)):
        if r.corrige_id is not None:
            corrections[_origine(r, par_id)] = r
    resultat = []
    for r in toutes:
        if r.corrige_id is not None:
            continue
        correction = corrections.get(r.revue_id)
        resultat.append(r if correction is None else replace(r, note=correction.note))
    return sorted(resultat, key=lambda r: (r.repondu_le, r.revue_id))


def rejouer(
    revues: Iterable[Revue],
    regles: ReglesAcquis,
    canonique: Callable[[str], str] | None = None,
) -> list[EtatConcept]:
    """Reconstruit l'état de chaque (élève, concept) à partir du seul journal.

    `canonique` (ex. `Bibliotheque.canonique`) regroupe sous l'identifiant actuel les revues
    d'un concept renommé (#20) : un seul état FSRS par concept."""
    cumuls: dict[tuple[str, str], _Cumul] = {}
    for r in effectives(revues):
        if r.nature == "pre_test":
            continue  # #7 : un pré-test raté est attendu, il ne pèse pas sur FSRS
        concept = canonique(r.concept_id) if canonique else r.concept_id
        cle = (r.brainiac_id, concept)
        cumul = cumuls.get(cle)
        if cumul is None:
            cumul = cumuls[cle] = _Cumul(carte_neuve(r.repondu_le))
        cumul.carte = reviser(cumul.carte, r.note, r.repondu_le)
        cumul.nb_revues += 1
        if r.nature == "transfert" and r.note >= NOTE_REUSSIE:
            cumul.transferts_reussis += 1
        if cumul.acquis_le is None and regle_satisfaite(
            cumul.carte, cumul.transferts_reussis, regles
        ):
            cumul.acquis_le = r.repondu_le  # A7 : fixé une fois, ne recule jamais
    return [
        EtatConcept(
            brainiac_id=brainiac_id,
            concept_id=concept_id,
            carte_json=vers_json(c.carte),
            nb_revues=c.nb_revues,
            acquis_le=c.acquis_le,
        )
        for (brainiac_id, concept_id), c in sorted(cumuls.items())
    ]
