"""Carte visuelle en Mermaid (#5) : relue à la gate de `02_carte`, puis colorée par maîtrise.

Prérequis en flèches pleines, liens latéraux en pointillés étiquetés par leur nature.
"""

from __future__ import annotations

from freinet.contenu import Carte

COULEURS = {
    "acquis": "fill:#2e7d32,color:#fff",
    "en_cours": "fill:#f9a825,color:#000",
    "debloque": "fill:#fff,stroke:#2e7d32",
    "verrouille": "fill:#eee,color:#888",
}


# Mots-clés Mermaid qui cassent le rendu s'ils servent d'identifiant de nœud.
RESERVES = frozenset(
    ("end", "graph", "subgraph", "style", "class", "classdef", "default", "click")
    + ("linkstyle", "direction")
)


def _noeud(identifiant: str) -> str:
    """Identifiant Mermaid : `-` devient `_` (jamais présent dans un id kebab-case)."""
    noeud = identifiant.replace("-", "_")
    return f"n_{noeud}" if noeud in RESERVES else noeud


def _etiquette(titre: str) -> str:
    return titre.replace('"', "#quot;").replace("\n", " ")


def mermaid(carte: Carte, titres: dict[str, str], etats: dict[str, str] | None = None) -> str:
    """`graph TD` de la carte ; `etats` (concept → acquis|en_cours|debloque|verrouille) colore."""
    lignes = ["graph TD"]
    for concept in carte.concepts:
        lignes.append(f'    {_noeud(concept)}["{_etiquette(titres.get(concept, concept))}"]')
    for avant, apres in carte.prerequis:
        lignes.append(f"    {_noeud(avant)} --> {_noeud(apres)}")
    for lien in carte.lateraux:
        lignes.append(f"    {_noeud(lien.de)} -. {lien.nature} .-> {_noeud(lien.vers)}")
    if etats:
        for etat, style in COULEURS.items():
            lignes.append(f"    classDef {etat} {style}")
        for concept in carte.concepts:
            if concept in etats:
                lignes.append(f"    class {_noeud(concept)} {etats[concept]}")
    return "\n".join(lignes) + "\n"
