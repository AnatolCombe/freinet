"""Chargement et validation de `bibliotheque/` (Knowledge bundle), identifiants immuables (#20).

Une surcouche par langue (`en/`, PROF-12) traduit les textes sans toucher à la structure :
mêmes identifiants, même domaine, mêmes liens ; `charger(racine, "en")` superpose les textes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import cached_property
from pathlib import Path
from typing import Protocol, TypeVar

from freinet.contenu import (
    Carte,
    Concept,
    Question,
    Quete,
    lire_carte,
    lire_concept,
    lire_question,
    lire_quete,
)
from freinet.frontmatter import ErreurContenu
from freinet.graphe import erreurs_carte
from freinet.langue import LANGUE_PAR_DEFAUT, LANGUES, libelles

T = TypeVar("T")


class _AvecId(Protocol):
    @property
    def id(self) -> str: ...


E = TypeVar("E", bound=_AvecId)

RACINE_BIBLIOTHEQUE = Path(__file__).resolve().parent.parent / "bibliotheque"


@dataclass(frozen=True)
class Bibliotheque:
    concepts: dict[str, Concept]
    cartes: dict[str, Carte]
    quetes: dict[str, Quete]
    questions: dict[str, Question]
    # Ce que la surcouche d'une langue a remplacé : « concepts/<id> », « questions/<id> »,
    # « quetes/<id> », « cartes/<id> » (vide en français, PROF-12).
    traduits: frozenset[str] = field(default_factory=frozenset)

    @cached_property
    def _alias(self) -> dict[str, str]:
        return {alias: c.id for c in self.concepts.values() for alias in c.alias}

    def canonique(self, identifiant: str) -> str:
        """Résout un alias vers l'identifiant actuel du concept (inchangé sinon)."""
        return self._alias.get(identifiant, identifiant)

    def concepts_connus(self) -> set[str]:
        """Identifiants et alias de concepts : ce qu'une revue peut référencer (#20)."""
        return set(self.concepts) | set(self._alias)


def _indexer(elements: list[tuple[Path, T]], cle: str) -> dict[str, T]:
    rangement: dict[str, T] = {}
    for chemin, element in elements:
        identifiant = getattr(element, cle)
        if chemin.stem != identifiant:
            raise ErreurContenu(chemin, f"le nom du fichier doit être {identifiant}.md")
        if identifiant in rangement:
            raise ErreurContenu(chemin, f"identifiant en double {identifiant!r}")
        rangement[identifiant] = element
    return rangement


def _question(chemin: Path) -> Question:
    question = lire_question(chemin)
    if chemin.parent.name != question.concept:
        raise ErreurContenu(chemin, f"la question doit vivre dans questions/{question.concept}/")
    return question


FICHIERS_RACINE = ("index.md", "CONTEXT.md")
MOTIFS = ("concepts/*.md", "cartes/*.md", "quetes/*.md", "questions/*/*.md")
SURCOUCHES = tuple(langue for langue in LANGUES if langue != LANGUE_PAR_DEFAUT)


def _refuser_fichiers_egares(racine: Path) -> None:
    """Un .md hors de l'arborescence attendue ne serait jamais chargé : c'est une erreur. Une
    surcouche (`en/`) reprend la même arborescence."""
    attendus = {racine / nom for nom in FICHIERS_RACINE}
    for base in (racine, *(racine / langue for langue in SURCOUCHES)):
        for motif in MOTIFS:
            attendus.update(base.glob(motif))
    for chemin in sorted(racine.rglob("*")):
        if chemin.is_file() and chemin.suffix.lower() == ".md" and chemin not in attendus:
            raise ErreurContenu(
                chemin, "fichier hors de concepts/, cartes/, quetes/, questions/<concept>/"
            )


def charger(racine: Path = RACINE_BIBLIOTHEQUE, langue: str = LANGUE_PAR_DEFAUT) -> Bibliotheque:
    """Lit tous les fichiers ; la première erreur de format arrête tout (ErreurContenu). Hors
    français, les textes de `racine/<langue>/` remplacent ceux qu'ils traduisent."""
    libelles(langue)  # ValueError si la langue n'est pas prise en charge
    if not racine.is_dir():
        raise ErreurContenu(racine, "dossier de bibliothèque introuvable")
    _refuser_fichiers_egares(racine)
    bib = Bibliotheque(
        concepts=_indexer(
            [(p, lire_concept(p)) for p in sorted(racine.glob("concepts/*.md"))], "id"
        ),
        cartes=_indexer([(p, lire_carte(p)) for p in sorted(racine.glob("cartes/*.md"))], "id"),
        quetes=_indexer([(p, lire_quete(p)) for p in sorted(racine.glob("quetes/*.md"))], "id"),
        questions=_indexer(
            [(p, _question(p)) for p in sorted(racine.glob("questions/*/*.md"))], "id"
        ),
    )
    return bib if langue == LANGUE_PAR_DEFAUT else superposer(bib, racine / langue)


# Ce qu'une traduction ne change pas : tout sauf les textes (spec PROF-12, décision 4).
STRUCTURE = {
    "concepts": ("id", "domaine", "alias", "origine", "projet"),
    "questions": ("id", "concept", "nature", "difficulte"),
    "quetes": ("id", "carte", "chemin"),
    "cartes": ("id", "concepts", "prerequis", "lateraux", "quetes"),
}


def _superposer_sorte(
    rang: dict[str, E],
    dossier: Path,
    sorte: str,
    motif: str,
    lire_un: Callable[[Path], E],
    traduits: set[str],
) -> dict[str, E]:
    """Le rang d'une sorte d'entités, chaque traduction à la place de l'original ; une structure
    différente du français, ou une entité inconnue en français, est une erreur de contenu."""
    resultat = dict(rang)
    for chemin in sorted(dossier.glob(motif)):
        traduit = lire_un(chemin)
        identifiant = str(traduit.id)
        if chemin.stem != identifiant:
            raise ErreurContenu(chemin, f"le nom du fichier doit être {identifiant}.md")
        original = rang.get(identifiant)
        if original is None:
            raise ErreurContenu(chemin, f"{identifiant} absent de la bibliothèque française")
        for champ in STRUCTURE[sorte]:
            avant, apres = getattr(original, champ), getattr(traduit, champ)
            if avant != apres:
                raise ErreurContenu(
                    chemin, f"{champ} différent de la version française ({avant!r} ≠ {apres!r})"
                )
        resultat[identifiant] = traduit
        traduits.add(f"{sorte}/{identifiant}")
    return resultat


def superposer(bib: Bibliotheque, dossier: Path) -> Bibliotheque:
    """La bibliothèque dont chaque entité traduite dans `dossier` prend le texte traduit."""
    traduits: set[str] = set()
    concepts = _superposer_sorte(
        bib.concepts, dossier, "concepts", "concepts/*.md", lire_concept, traduits
    )
    questions = _superposer_sorte(
        bib.questions, dossier, "questions", "questions/*/*.md", _question, traduits
    )
    quetes = _superposer_sorte(bib.quetes, dossier, "quetes", "quetes/*.md", lire_quete, traduits)
    cartes = _superposer_sorte(bib.cartes, dossier, "cartes", "cartes/*.md", lire_carte, traduits)
    return replace(
        bib,
        concepts=concepts,
        questions=questions,
        quetes=quetes,
        cartes=cartes,
        traduits=frozenset(traduits),
    )


def manquants(bib: Bibliotheque, cartes: list[str]) -> list[str]:
    """Ce qui reste en français dans ces cartes (carte, concepts, leurs questions, quêtes)."""
    attendus: list[str] = []
    for carte_id in cartes:
        carte = bib.cartes.get(carte_id)
        if carte is None:
            continue
        attendus.append(f"cartes/{carte.id}")
        for concept_id in carte.concepts:
            attendus.append(f"concepts/{concept_id}")
            attendus += sorted(
                f"questions/{q.id}" for q in bib.questions.values() if q.concept == concept_id
            )
        attendus += [f"quetes/{q}" for q in carte.quetes]
    return [a for a in dict.fromkeys(attendus) if a not in bib.traduits]


def erreurs(bib: Bibliotheque) -> list[str]:
    """Tout ce qui interdit de publier la bibliothèque (inv. 8) ; liste vide = publiable."""
    problemes: list[str] = []
    connus = set(bib.concepts)
    proprietaires: dict[str, list[str]] = {}
    for concept in bib.concepts.values():
        for alias in concept.alias:
            if alias in connus:
                problemes.append(f"{concept.id} : l'alias {alias} est l'identifiant d'un concept")
            proprietaires.setdefault(alias, []).append(concept.id)
    for alias, ids in sorted(proprietaires.items()):
        if len(ids) > 1:
            problemes.append(f"alias {alias} revendiqué par {' et '.join(sorted(ids))}")
    for carte in bib.cartes.values():
        problemes.extend(erreurs_carte(carte, connus))
        for id_quete in carte.quetes:
            if id_quete not in bib.quetes:
                problemes.append(f"{carte.id} : quête inconnue {id_quete}")
    for quete in bib.quetes.values():
        sa_carte = bib.cartes.get(quete.carte)
        if sa_carte is None:
            problemes.append(f"{quete.id} : carte inconnue {quete.carte}")
            continue
        for etape in quete.chemin:
            if etape not in sa_carte.concepts:
                problemes.append(f"{quete.id} : {etape} n'est pas dans la carte {sa_carte.id}")
    for question in bib.questions.values():
        if question.concept not in connus:
            problemes.append(f"{question.id} : concept inconnu {question.concept}")
    return problemes


def concepts_disparus(references: set[str], bib: Bibliotheque) -> set[str]:
    """Concepts cités par le journal `revue` que la bibliothèque ne connaît plus (#20).

    Seuls les identifiants de concept sont immuables : l'état FSRS suit le concept (A8), une
    question peut donc être retirée ; un concept renommé garde son ancien id dans `alias:`."""
    return references - bib.concepts_connus()
