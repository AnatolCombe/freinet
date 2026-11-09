"""Validation du contenu fabriqué par le fan-out (#79), en plus de `bibliotheque.erreurs`.

Domaine déclaré au registre, texte imprimable par la police du ticket (sinon un « ≥ »
disparaîtrait en silence), leçon ≤ 400 caractères et au moins une analogie
(`_config/pedagogie.md`), sources au registre (#47), finance sourcée et avertie (inv. 9),
4 à 6 questions révisables par concept dont au moins une de transfert (A8 : sans elle,
« acquis » est impossible), et au plus un pré-test (il ne pèse pas sur FSRS).
"""

from __future__ import annotations

import re
import unicodedata

from freinet.bibliotheque import Bibliotheque
from freinet.imprimable import absents
from freinet.langue import FR, LANGUE_PAR_DEFAUT, Libelles
from freinet.sources import DOMAINE_COMMUN, Registre, refus

LECON_MAX = 400
EXPLICATION_MAX = 400
QUESTIONS_MIN, QUESTIONS_MAX = 4, 6
PRE_TESTS_MAX = 1
# Ce qui s'imprime est du texte brut : ni lien, ni adresse, ni balisage (#45).
_LIEN_OU_BALISE = re.compile(
    r"://|\bwww\.|\]\(|<[a-zA-Z/!]|\b(?:javascript|data|mailto|vbscript|file):",
    re.IGNORECASE,
)


def contient_lien(texte: str) -> bool:
    """Lien, adresse ou balisage : interdit dans tout ce qui s'imprime (#45)."""
    return bool(_LIEN_OU_BALISE.search(texte))


def _normaliser(texte: str) -> str:
    """Compare des phrases sans se soucier des apostrophes, espaces, casse ni composition."""
    texte = unicodedata.normalize("NFC", texte).replace("’", "'").casefold()
    return " ".join(texte.split())


def erreurs_contenu(bib: Bibliotheque, registre: Registre, lib: Libelles = FR) -> list[str]:
    """Hors français, seuls les textes traduits (`bib.traduits`) sont jugés, avec l'avertissement
    finance de leur langue ; le reste a été jugé en français (PROF-12)."""

    def juge(sorte: str, identifiant: str) -> bool:
        return lib.code == LANGUE_PAR_DEFAUT or f"{sorte}/{identifiant}" in bib.traduits

    problemes: list[str] = []
    questions: dict[str, list[str]] = {}
    for question in bib.questions.values():
        questions.setdefault(question.concept, []).append(question.nature)
    avertissement = _normaliser(lib.avertissement_finance)
    for question in sorted(bib.questions.values(), key=lambda q: q.id):
        if not juge("questions", question.id):
            continue
        for champ, texte in (
            ("l'énoncé", question.enonce),
            ("la réponse", question.reponse),
            ("l'explication", question.explication),
        ):
            if _LIEN_OU_BALISE.search(texte):
                problemes.append(f"{question.id} : lien ou balisage dans {champ} (#45)")
            if manque := absents(texte):
                problemes.append(
                    f"{question.id} : caractères non imprimables dans {champ} : {manque}"
                )
        if len(question.explication) > EXPLICATION_MAX:
            problemes.append(
                f"{question.id} : explication de {len(question.explication)} caractères "
                f"(max {EXPLICATION_MAX})"
            )
    for concept in sorted(bib.concepts.values(), key=lambda c: c.id):
        if not juge("concepts", concept.id):
            continue
        cid = concept.id
        if concept.domaine not in registre.par_domaine or concept.domaine == DOMAINE_COMMUN:
            problemes.append(
                f"{cid} : domaine inconnu {concept.domaine!r} "
                "(créer _config/sources/<domaine>.md, même sans URL)"
            )
        if len(concept.lecon) > LECON_MAX:
            problemes.append(f"{cid} : leçon de {len(concept.lecon)} caractères (max {LECON_MAX})")
        if not concept.analogies:
            problemes.append(f"{cid} : aucune analogie (section « ## Analogies »)")
        textes = [
            ("leçon", concept.lecon),
            ("version longue", concept.version_longue),
            ("analogies", concept.analogies),
            *[("anecdote", a.texte) for a in concept.anecdotes],
        ]
        for champ, texte in [("titre", concept.titre), *textes]:
            if _LIEN_OU_BALISE.search(texte):
                problemes.append(f"{cid} : lien ou balisage dans {champ} (#45)")
            if manque := absents(texte):
                problemes.append(f"{cid} : caractères non imprimables dans {champ} : {manque}")
        references = [a.source for a in concept.anecdotes] + [s.reference for s in concept.sources]
        for reference in references:
            raison = refus(reference, concept.domaine, registre)
            if raison:
                problemes.append(f"{cid} : {raison}")
        if (concept.origine is None) != (concept.projet is None):
            problemes.append(f"{cid} : `origine` et `projet` vont ensemble (B28)")
        if concept.domaine == "finance":
            if not concept.sources:
                problemes.append(f"{cid} : concept finance sans source (inv. 9)")
            if avertissement not in _normaliser(f"{concept.lecon}\n{concept.version_longue}"):
                problemes.append(f"{cid} : avertissement finance absent (inv. 9, B26)")
        natures = questions.get(cid, [])
        revisables = [n for n in natures if n != "pre_test"]
        if not QUESTIONS_MIN <= len(revisables) <= QUESTIONS_MAX:
            problemes.append(
                f"{cid} : {len(revisables)} question(s) révisable(s) "
                f"(attendu {QUESTIONS_MIN} à {QUESTIONS_MAX}, pré-tests exclus)"
            )
        if natures.count("pre_test") > PRE_TESTS_MAX:
            problemes.append(f"{cid} : {natures.count('pre_test')} pré-tests (max {PRE_TESTS_MAX})")
        if "transfert" not in natures:
            problemes.append(f"{cid} : aucune question de transfert (A8)")
    return problemes
