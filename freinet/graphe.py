"""Le graphe d'une carte : validation (inv. 8, #4), ordre de déblocage, état de maîtrise.

Les prérequis appartiennent à la carte, pas au concept (brainstorm §6.1) ; `graphlib`
(stdlib) suffit, networkx n'apporte rien ici.
"""

from __future__ import annotations

from collections import Counter
from graphlib import CycleError, TopologicalSorter

from freinet.contenu import Carte


def _graphe(carte: Carte) -> dict[str, set[str]]:
    """concept → ses prérequis directs, limités aux concepts de la carte."""
    graphe: dict[str, set[str]] = {c: set() for c in carte.concepts}
    for avant, apres in carte.prerequis:
        if avant in graphe and apres in graphe and avant != apres:
            graphe[apres].add(avant)
    return graphe


def erreurs_carte(carte: Carte, ids_concepts: set[str]) -> list[str]:
    """Tout ce qui interdit de publier la carte ; liste vide = carte valide.

    `ids_concepts` : identifiants actuels des concepts, sans alias (une carte cite l'id actuel)."""
    erreurs: list[str] = []
    dans_carte = set(carte.concepts)
    for doublon, nombre in sorted(Counter(carte.concepts).items()):
        if nombre > 1:
            erreurs.append(f"{carte.id} : concept {doublon} listé {nombre} fois")
    for inconnu in sorted(dans_carte - ids_concepts):
        erreurs.append(f"{carte.id} : concept inconnu {inconnu}")
    for avant, apres in carte.prerequis:
        for bout in (avant, apres):
            if bout not in dans_carte:
                erreurs.append(f"{carte.id} : prérequis {avant} → {apres} hors carte ({bout})")
        if avant == apres:
            erreurs.append(f"{carte.id} : {avant} est son propre prérequis")
    for lien in carte.lateraux:
        for bout in (lien.de, lien.vers):
            if bout not in dans_carte:
                erreurs.append(
                    f"{carte.id} : lien latéral {lien.de} ~ {lien.vers} hors carte ({bout})"
                )
        if lien.de == lien.vers:
            erreurs.append(f"{carte.id} : lien latéral de {lien.de} vers lui-même")
    try:
        tuple(TopologicalSorter(_graphe(carte)).static_order())
    except CycleError as cycle:
        erreurs.append(f"{carte.id} : cycle de prérequis {' → '.join(cycle.args[1])}")
    if len(dans_carte) > 1:
        relies = {c for paire in carte.prerequis for c in paire}
        relies |= {c for lien in carte.lateraux for c in (lien.de, lien.vers)}
        for orphelin in sorted(dans_carte - relies):
            erreurs.append(f"{carte.id} : concept orphelin {orphelin} (aucun lien)")
    return erreurs


def ordre_deblocage(carte: Carte) -> list[str]:
    """Un ordre topologique déterministe : à égalité, l'ordre alphabétique.

    Précondition : carte valide (`erreurs_carte(...) == []`) ; un cycle lève CycleError."""
    tri = TopologicalSorter(_graphe(carte))
    tri.prepare()
    ordre: list[str] = []
    while tri.is_active():
        prets = sorted(tri.get_ready())
        ordre.extend(prets)
        tri.done(*prets)
    return ordre


def etats_maitrise(carte: Carte, acquis: set[str], en_cours: set[str]) -> dict[str, str]:
    """acquis > en_cours > debloque (tous ses prérequis directs acquis) > verrouille.

    Un concept acquis le reste même si un prérequis ne l'est pas (A7). Précondition : carte
    valide (`erreurs_carte(...) == []`)."""
    prerequis = _graphe(carte)
    etats: dict[str, str] = {}
    for concept in carte.concepts:
        if concept in acquis:
            etats[concept] = "acquis"
        elif concept in en_cours:
            etats[concept] = "en_cours"
        elif prerequis[concept] <= acquis:
            etats[concept] = "debloque"
        else:
            etats[concept] = "verrouille"
    return etats
