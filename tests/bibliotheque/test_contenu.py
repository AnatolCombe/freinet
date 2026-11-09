from pathlib import Path

import pytest

from freinet.contenu import (
    Anecdote,
    Lateral,
    lire_carte,
    lire_concept,
    lire_question,
    lire_quete,
)
from freinet.frontmatter import ErreurContenu
from tests.bibliotheque.demo import DEMO, ecrire


def test_concept_de_demo() -> None:
    concept = lire_concept(DEMO / "concepts" / "cadence-parfaite.md")
    assert (concept.id, concept.domaine) == ("cadence-parfaite", "musique")
    assert concept.lecon.startswith("Dominante puis tonique")
    assert concept.anecdotes[0] == Anecdote(
        "Rameau théorise la basse fondamentale en 1722.",
        "https://fr.wikipedia.org/wiki/Trait%C3%A9_de_l%27harmonie",
    )


def test_carte_quete_question_de_demo() -> None:
    carte = lire_carte(DEMO / "cartes" / "harmonie-demo.md")
    assert carte.prerequis[0] == ("intervalle", "accord-parfait")
    assert carte.lateraux == (Lateral("cadence-parfaite", "intervalle", "analogie"),)
    quete = lire_quete(DEMO / "quetes" / "entendre-une-cadence.md")
    assert quete.chemin[-1] == "cadence-parfaite"
    question = lire_question(DEMO / "questions" / "intervalle" / "intervalle-q2.md")
    assert (question.nature, question.difficulte) == ("transfert", 3)


@pytest.mark.parametrize(
    ("texte", "message"),
    [
        ("---\ntype: carte\nid: x\n---\n", "type attendu 'concept'"),
        ("---\ntype: concept\nid: Pas_Kebab\ntitre: T\ndomaine: d\n---\n", "identifiant invalide"),
        ("---\ntype: concept\nid: x\ndomaine: d\n---\n", "'titre'"),
        (
            "---\ntype: concept\nid: x\ntitre: T\ndomaine: d\n"
            "anecdotes: [{texte: sans source}]\n---\n",
            "sans source",
        ),
        ("---\ntype: concept\nid: x\ntitre: T\ndomaine: d\nalias: pas-une-liste\n---\n", "liste"),
        ("---\ntype: concept\nid: x\ntitre: No\ndomaine: d\n---\n", "'titre'"),
        (
            "---\ntype: concept\nid: x\ntitre: T\ndomaine: d\n---\n\n## Version longue\n\nV.\n",
            "Leçon",
        ),
        (
            "---\ntype: concept\nid: x\ntitre: T\ndomaine: d\n"
            "anecdotes: [{texte: '  ', source: s}]\n---\n",
            "sans texte",
        ),
    ],
)
def test_concept_invalide_refuse(tmp_path: Path, texte: str, message: str) -> None:
    fichier = tmp_path / "x.md"
    ecrire(fichier, texte)
    with pytest.raises(ErreurContenu, match=message):
        lire_concept(fichier)


@pytest.mark.parametrize(
    ("corps", "message"),
    [
        ("prerequis: [[a]]", "prérequis invalide"),
        ("prerequis: [[a, B]]", "prérequis invalide"),
        ("lateraux: [{de: a, vers: b, nature: amitie}]", "latéral invalide"),
        ("lateraux: [pas-un-dict]", "dictionnaires"),
        ("lateraux: [{de: A, vers: b, nature: analogie}]", "latéral invalide"),
        ("prerequis: 5", "liste attendue"),
    ],
)
def test_carte_invalide_refusee(tmp_path: Path, corps: str, message: str) -> None:
    fichier = tmp_path / "x.md"
    ecrire(fichier, f"---\ntype: carte\nid: x\nconcepts: [a, b]\n{corps}\n---\n")
    with pytest.raises(ErreurContenu, match=message):
        lire_carte(fichier)


@pytest.mark.parametrize(
    ("champs", "message"),
    [
        ("nature: devinette\ndifficulte: 2", "nature de question inconnue"),
        ("nature: rappel\ndifficulte: 9", "difficulte"),
        ("nature: rappel\ndifficulte: true", "difficulte"),
    ],
)
def test_question_invalide_refusee(tmp_path: Path, champs: str, message: str) -> None:
    fichier = tmp_path / "q.md"
    ecrire(
        fichier, f"---\ntype: question\nid: q\nconcept: c\n{champs}\nenonce: E\nreponse: R\n---\n"
    )
    with pytest.raises(ErreurContenu, match=message):
        lire_question(fichier)


def test_carte_sans_prerequis_ni_lateraux(tmp_path: Path) -> None:
    fichier = tmp_path / "x.md"
    ecrire(fichier, "---\ntype: carte\nid: x\nconcepts: [a]\nprerequis:\nlateraux:\n---\n")
    carte = lire_carte(fichier)
    assert (carte.prerequis, carte.lateraux) == ((), ())


def test_sources_et_champs_facultatifs(tmp_path: Path) -> None:
    fichier = tmp_path / "x.md"
    ecrire(
        fichier,
        "---\ntype: concept\nid: x\ntitre: T\ndomaine: d\norigine: ~/R/c.md\nprojet: R\n"
        "sources: [{url: 'https://a.org/p', titre: A}, {ouvrage: 'McKee, Story (1997)'}]\n---\n"
        "## Leçon\nL.\n\n## Version longue\nV.\n\n## Analogies\nA.\n",
    )
    concept = lire_concept(fichier)
    assert [(s.reference, s.titre) for s in concept.sources] == [
        ("https://a.org/p", "A"),
        ("McKee, Story (1997)", ""),
    ]
    assert (concept.version_longue, concept.analogies) == ("V.", "A.")
    assert (concept.origine, concept.projet) == ("~/R/c.md", "R")


@pytest.mark.parametrize(
    ("sources", "message"),
    [
        ("[{titre: A}]", "exactement un"),
        ("[{url: 'https://a.org', ouvrage: 'X, Y (2000)'}]", "exactement un"),
        ("[{url: ''}]", "exactement un"),
        ("[{ouvrage: 'X, Y (2000)', titre: 1984}]", "`titre` doit être un texte"),
    ],
)
def test_source_mal_formee_refusee(tmp_path: Path, sources: str, message: str) -> None:
    fichier = tmp_path / "x.md"
    ecrire(fichier, f"---\ntype: concept\nid: x\ntitre: T\ndomaine: d\nsources: {sources}\n---\n")
    with pytest.raises(ErreurContenu, match=message):
        lire_concept(fichier)


def test_champs_facultatifs_absents_et_origine_non_textuelle(tmp_path: Path) -> None:
    concept = lire_concept(DEMO / "concepts" / "intervalle.md")
    assert (concept.sources, concept.origine, concept.projet) == ((), None, None)
    fichier = tmp_path / "x.md"
    ecrire(
        fichier,
        "---\ntype: concept\nid: x\ntitre: T\ndomaine: d\norigine: 2026-01-01\n---\n## Leçon\nL.\n",
    )
    with pytest.raises(ErreurContenu, match="'origine'"):
        lire_concept(fichier)


def test_titre_de_carte_facultatif(tmp_path: Path) -> None:
    chemin = tmp_path / "carte.md"
    chemin.write_text(
        "---\ntype: carte\nid: demo\ntitre: Day trading\nconcepts: [a]\n---\n", encoding="utf-8"
    )
    assert lire_carte(chemin).titre == "Day trading"
    chemin.write_text("---\ntype: carte\nid: demo\nconcepts: [a]\n---\n", encoding="utf-8")
    assert lire_carte(chemin).titre is None
