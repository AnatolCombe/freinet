from pathlib import Path

import pytest

from freinet.base import Base
from freinet.bibliotheque import charger, concepts_disparus, erreurs
from freinet.frontmatter import ErreurContenu
from tests.bibliotheque.demo import DEMO, copie_demo, ecrire
from tests.socle.fabrique import revue

QUESTION = (
    "---\ntype: question\nid: {id}\nconcept: {concept}\nnature: rappel\n"
    "enonce: E\nreponse: R\ndifficulte: 1\n---\n"
)


def test_demo_valide() -> None:
    bib = charger(DEMO)
    assert erreurs(bib) == []
    assert bib.canonique("intervalles") == "intervalle"
    assert bib.canonique("inconnu") == "inconnu"


def test_bibliotheque_vide(tmp_path: Path) -> None:
    bib = charger(tmp_path)
    assert (bib.concepts, bib.cartes, erreurs(bib)) == ({}, {}, [])


def test_racine_introuvable_refusee(tmp_path: Path) -> None:
    with pytest.raises(ErreurContenu, match="introuvable"):
        charger(tmp_path / "faute-de-frappe")


@pytest.mark.parametrize(
    "egare",
    ["questions/perdue.md", "concepts/sous/x.md", "concepts/Autre.MD", "notes.md"],
)
def test_fichier_egare_refuse(tmp_path: Path, egare: str) -> None:
    racine = copie_demo(tmp_path)
    ecrire(racine / egare, "---\ntype: concept\n---\n")
    with pytest.raises(ErreurContenu, match="hors de concepts/"):
        charger(racine)


def test_nom_de_fichier_different_de_l_id_refuse(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    ecrire(
        racine / "concepts" / "autre.md",
        "---\ntype: concept\nid: intervalle-bis\ntitre: T\ndomaine: musique\n---\n## Leçon\nL.\n",
    )
    with pytest.raises(ErreurContenu, match="intervalle-bis.md"):
        charger(racine)


def test_question_hors_du_dossier_de_son_concept_refusee(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    ecrire(
        racine / "questions" / "intervalle" / "q9.md",
        QUESTION.format(id="q9", concept="accord-parfait"),
    )
    with pytest.raises(ErreurContenu, match="questions/accord-parfait/"):
        charger(racine)


def test_identifiant_en_double_refuse(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    ecrire(
        racine / "questions" / "accord-parfait" / "intervalle-q1.md",
        QUESTION.format(id="intervalle-q1", concept="accord-parfait"),
    )
    with pytest.raises(ErreurContenu, match="en double"):
        charger(racine)


def test_references_cassees_signalees(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    ecrire(
        racine / "quetes" / "perdue.md",
        "---\ntype: quete\nid: perdue\ncarte: absente\nobjectif: O\nchemin: [intervalle]\n---\n",
    )
    ecrire(
        racine / "quetes" / "egaree.md",
        "---\ntype: quete\nid: egaree\ncarte: harmonie-demo\nobjectif: O\nchemin: [solfege]\n---\n",
    )
    ecrire(
        racine / "questions" / "fantome" / "x-q1.md", QUESTION.format(id="x-q1", concept="fantome")
    )
    ecrire(
        racine / "questions" / "intervalles" / "y-q1.md",
        QUESTION.format(id="y-q1", concept="intervalles"),
    )
    carte = (racine / "cartes" / "harmonie-demo.md").read_text(encoding="utf-8")
    ecrire(
        racine / "cartes" / "harmonie-demo.md",
        carte.replace("quetes: [entendre-une-cadence]", "quetes: [entendre-une-cadence, absente]"),
    )
    assert erreurs(charger(racine)) == [
        "harmonie-demo : quête inconnue absente",
        "egaree : solfege n'est pas dans la carte harmonie-demo",
        "perdue : carte inconnue absente",
        "x-q1 : concept inconnu fantome",
        # le contenu publié cite l'identifiant actuel, jamais un alias
        "y-q1 : concept inconnu intervalles",
    ]


def test_alias_en_conflit(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    for nom, alias in (("a", "[accord-parfait]"), ("b", "[intervalles]")):
        ecrire(
            racine / "concepts" / f"{nom}.md",
            f"---\ntype: concept\nid: {nom}\ntitre: T\ndomaine: musique\nalias: {alias}\n---\n"
            "## Leçon\nL.\n",
        )
    probleme = "\n".join(erreurs(charger(racine)))
    assert "l'alias accord-parfait est l'identifiant d'un concept" in probleme
    assert "alias intervalles revendiqué par b et intervalle" in probleme


def test_concept_reference_disparu_detecte() -> None:
    bib = charger(DEMO)
    with Base(":memory:") as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        base.ajouter_revue(revue("r1", brainiac_id=b, concept_id="intervalles"))
        base.ajouter_revue(revue("r2", brainiac_id=b, concept_id="renomme-sans-alias"))
        base.ajouter_revue(revue("r3", brainiac_id=b, concept_id="intervalle"))
        references = base.concepts_references()
    assert references == {"intervalles", "renomme-sans-alias", "intervalle"}
    # l'ancien id gardé en alias est connu ; la question d'un concept retiré ne bloque rien
    assert concepts_disparus(references, bib) == {"renomme-sans-alias"}
