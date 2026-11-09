"""Réutiliser plutôt que créer (#43) : les concepts existants proches d'un concept candidat.

Sert à `fanout/02_carte` : le script rend un texte que l'étape LLM lit (inv. 2 : le LLM ne
lit jamais la base). Un homonyme d'un autre domaine est signalé, jamais fusionné.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from freinet.base import IndexConcepts
from freinet.bibliotheque import RACINE_BIBLIOTHEQUE, Bibliotheque, charger
from freinet.frontmatter import ErreurContenu

NB_CANDIDATS = 5
MOTS_VIDES = frozenset(
    ("les", "des", "une", "aux", "sur", "par", "pour", "dans", "avec", "sans") + ("the", "and")
)


@dataclass(frozen=True)
class Candidat:
    id: str
    titre: str
    domaine: str
    autre_domaine: bool


def _singulier(mot: str) -> str:
    """Pluriel français simple : « accords » cherche « accord* » (pas « virus », « choix »)."""
    if len(mot) >= 5 and mot[-1] in "sx" and not mot.endswith(("us", "is", "ix")):
        return mot[:-1]
    return mot


def _domaine(domaine: str) -> str:
    return domaine.strip().casefold()


def _mots(texte: str) -> list[str]:
    """Les mots porteurs de sens : ni mots vides ni mots de moins de 3 lettres."""
    return [
        _singulier(m)
        for m in re.findall(r"\w+", texte.lower())
        if len(m) >= 3 and m not in MOTS_VIDES
    ]


def candidats(bib: Bibliotheque, texte: str, domaine: str, n: int = NB_CANDIDATS) -> list[Candidat]:
    entrees = (
        (c.id, c.titre, c.domaine, f"{c.id.replace('-', ' ')} {' '.join(c.alias)} {c.lecon}")
        for c in bib.concepts.values()
    )
    with IndexConcepts(entrees) as index:
        trouves = index.chercher(_mots(texte), n)
    return [
        Candidat(identifiant, titre, dom, _domaine(dom) != _domaine(domaine))
        for identifiant, titre, dom in trouves
    ]


def rapport(texte: str, domaine: str, trouves: list[Candidat]) -> str:
    lignes = [f"Candidats pour « {texte} » ({domaine}) :"]
    if not trouves:
        lignes.append("- aucun concept proche : créer un nouveau concept")
    for c in trouves:
        alerte = " ⚠ autre domaine : ne pas fusionner" if c.autre_domaine else ""
        lignes.append(f"- {c.id} — {c.titre} ({c.domaine}){alerte}")
    return "\n".join(lignes)


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("texte", help="titre ou description courte du concept candidat")
    lecteur.add_argument("--domaine", required=True)
    lecteur.add_argument("--bibliotheque", type=Path, default=RACINE_BIBLIOTHEQUE)
    options = lecteur.parse_args(arguments)
    try:
        bib = charger(options.bibliotheque)
    except ErreurContenu as erreur:
        print(f"bibliothèque illisible : {erreur}", file=sys.stderr)
        return 2
    print(rapport(options.texte, options.domaine, candidats(bib, options.texte, options.domaine)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
