from pathlib import Path

import pytest

from freinet.bibliotheque import charger
from freinet.langue import EN
from freinet.sources import lire_registre
from freinet.validation import erreurs_contenu
from tests.bibliotheque.demo import DEMO, copie_demo, ecrire, surcouche_en

REGISTRE = lire_registre()


def _concept(racine: Path, id_: str, entete: str, corps: str) -> None:
    ecrire(
        racine / "concepts" / f"{id_}.md", f"---\ntype: concept\nid: {id_}\n{entete}---\n{corps}"
    )


def _questions(racine: Path, concept: str, natures: list[str]) -> None:
    for i, nature in enumerate(natures, 1):
        ecrire(
            racine / "questions" / concept / f"{concept}-q{i}.md",
            f"---\ntype: question\nid: {concept}-q{i}\nconcept: {concept}\nnature: {nature}\n"
            "enonce: E\nreponse: R\ndifficulte: 1\n---\n",
        )


def test_demo_publiable() -> None:
    assert erreurs_contenu(charger(DEMO), REGISTRE) == []


def test_concept_finance_complet(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    _concept(
        racine,
        "interets-composes",
        "titre: Intérêts composés\ndomaine: finance\n"
        "sources: [{url: 'https://www.amf-france.org/fr/interets', titre: AMF}]\n",
        "## Leçon\nL'intérêt produit lui-même de l'intérêt.\n\n## Version longue\n"
        "Éducatif, pas un conseil d'investissement.\n\n## Analogies\nUne boule de neige.\n",
    )
    _questions(racine, "interets-composes", ["rappel", "application", "piege", "transfert"])
    assert erreurs_contenu(charger(racine), REGISTRE) == []


def test_tous_les_defauts_signales(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    _concept(
        racine,
        "levier",
        "titre: Levier\ndomaine: finance\norigine: ~/x.md\n"
        "anecdotes: [{texte: T, source: 'https://blog.example.com/levier'}]\n",
        "## Leçon\n" + "x" * 401 + "\n",
    )
    _questions(racine, "levier", ["rappel", "application", "piege"])
    assert erreurs_contenu(charger(racine), REGISTRE) == [
        "levier : leçon de 401 caractères (max 400)",
        "levier : aucune analogie (section « ## Analogies »)",
        "levier : source hors registre pour « finance » : 'https://blog.example.com/levier'",
        "levier : `origine` et `projet` vont ensemble (B28)",
        "levier : concept finance sans source (inv. 9)",
        "levier : avertissement finance absent (inv. 9, B26)",
        "levier : 3 question(s) révisable(s) (attendu 4 à 6, pré-tests exclus)",
        "levier : aucune question de transfert (A8)",
    ]


def _concept_musique(racine: Path, id_: str, lecon: str = "L.") -> None:
    _concept(
        racine, id_, "titre: T\ndomaine: musique\n", f"## Leçon\n{lecon}\n\n## Analogies\nA.\n"
    )


@pytest.mark.parametrize("domaine", ["Finance", "finances", "culture"])
def test_domaine_hors_registre_refuse(tmp_path: Path, domaine: str) -> None:
    racine = copie_demo(tmp_path)
    _concept(racine, "x", f"titre: T\ndomaine: {domaine}\n", "## Leçon\nL.\n\n## Analogies\nA.\n")
    _questions(racine, "x", ["rappel", "application", "piege", "transfert"])
    assert erreurs_contenu(charger(racine), REGISTRE) == [
        f"x : domaine inconnu {domaine!r} (créer _config/sources/<domaine>.md, même sans URL)"
    ]


@pytest.mark.parametrize(
    "phrase",
    [
        "Éducatif, pas un conseil d’investissement.",
        "Éducatif, pas un\nconseil d'investissement.",
        "ÉDUCATIF,  pas un conseil d'investissement.",
        "Éducatif, pas un conseil d'investissement.",
    ],
)
def test_avertissement_finance_tolerant(tmp_path: Path, phrase: str) -> None:
    racine = copie_demo(tmp_path)
    _concept(
        racine,
        "interets",
        "titre: I\ndomaine: finance\nsources: [{url: 'https://www.amf-france.org/x'}]\n",
        f"## Leçon\n{phrase}\n\n## Analogies\nA.\n",
    )
    _questions(racine, "interets", ["rappel", "application", "piege", "transfert"])
    assert erreurs_contenu(charger(racine), REGISTRE) == []


def test_bornes_lecon_et_nombre_de_questions(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    _concept_musique(racine, "juste", "x" * 400)
    _questions(racine, "juste", ["rappel", "application", "piege", "transfert", "rappel", "piege"])
    _concept_musique(racine, "trop")
    _questions(racine, "trop", ["rappel"] * 6 + ["transfert"])
    _concept_musique(racine, "pretests")
    _questions(racine, "pretests", ["pre_test", "pre_test", "rappel", "application", "transfert"])
    assert erreurs_contenu(charger(racine), REGISTRE) == [
        "pretests : 3 question(s) révisable(s) (attendu 4 à 6, pré-tests exclus)",
        "pretests : 2 pré-tests (max 1)",
        "trop : 7 question(s) révisable(s) (attendu 4 à 6, pré-tests exclus)",
    ]


def test_liens_et_balisage_refuses_dans_ce_qui_s_imprime(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    _concept(
        racine,
        "piege",
        "titre: T\ndomaine: musique\n"
        "anecdotes: [{texte: 'Voir [clic](javascript:x)', source: 'Auteur, Titre (1999)'}]\n",
        "## Leçon\nLire http://evil.example.com ici.\n\n## Analogies\nComme <b>ça</b>.\n",
    )
    _questions(racine, "piege", ["rappel", "application", "piege", "transfert"])
    ecrire(
        racine / "questions" / "piege" / "piege-q1.md",
        "---\ntype: question\nid: piege-q1\nconcept: piege\nnature: rappel\n"
        "enonce: 'Va sur www.exemple.fr'\nreponse: R\ndifficulte: 1\n---\n",
    )
    assert erreurs_contenu(charger(racine), REGISTRE) == [
        "piege-q1 : lien ou balisage dans l'énoncé (#45)",
        "piege : lien ou balisage dans leçon (#45)",
        "piege : lien ou balisage dans analogies (#45)",
        "piege : lien ou balisage dans anecdote (#45)",
    ]


def test_caracteres_non_imprimables_refuses(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    _concept(
        racine,
        "ecart",
        "titre: Écart ≥ seuil ☃\ndomaine: musique\n",
        "## Leçon\nUn rendement ≥ 5 %, π et √2 s'impriment ; pas 𝄞 ni 漢.\n\n"
        "## Analogies\nComme un escalier.\n",
    )
    _questions(racine, "ecart", ["rappel", "application", "piege", "transfert"])
    ecrire(
        racine / "questions" / "ecart" / "ecart-q1.md",
        "---\ntype: question\nid: ecart-q1\nconcept: ecart\nnature: rappel\n"
        "enonce: 'Combien ?'\nreponse: '🎵'\ndifficulte: 1\n---\n",
    )
    assert erreurs_contenu(charger(racine), REGISTRE) == [
        "ecart-q1 : caractères non imprimables dans la réponse : 🎵",
        "ecart : caractères non imprimables dans leçon : 漢𝄞",
    ]


def test_validation_de_la_traduction(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    en = surcouche_en(racine)
    assert (
        erreurs_contenu(charger(racine, "en"), REGISTRE, EN) == []
    )  # seul « intervalle » est jugé
    fichier = en / "concepts" / "intervalle.md"
    fichier.write_text(
        fichier.read_text(encoding="utf-8").replace(
            "## Analogies\n\nLike the distance between two steps of a staircase.\n", ""
        ),
        encoding="utf-8",
    )
    assert any("aucune analogie" in p for p in erreurs_contenu(charger(racine, "en"), REGISTRE, EN))


def test_finance_en_anglais_exige_l_avertissement_anglais(tmp_path: Path) -> None:
    from dataclasses import replace

    bib = charger(copie_demo(tmp_path))
    concept = replace(
        bib.concepts["intervalle"], domaine="finance",
        lecon="Risk. Educational, not investment advice.",
    )  # fmt: skip
    fr = replace(bib, concepts={**bib.concepts, "intervalle": concept})
    en = replace(fr, traduits=frozenset({"concepts/intervalle"}))
    assert any("avertissement finance" in p for p in erreurs_contenu(fr, REGISTRE))
    assert not any(
        "avertissement finance" in p and p.startswith("intervalle")
        for p in erreurs_contenu(en, REGISTRE, EN)
    )
