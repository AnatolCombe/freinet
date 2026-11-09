from pathlib import Path

import pytest

from freinet.bibliotheque import charger, manquants
from freinet.frontmatter import ErreurContenu
from tests.bibliotheque.demo import copie_demo, ecrire, surcouche_en


def test_sans_surcouche_tout_reste_en_francais(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    fr, en = charger(racine), charger(racine, "en")
    assert en.concepts == fr.concepts and en.traduits == frozenset()
    assert manquants(en, ["harmonie-demo"])[0] == "cartes/harmonie-demo"


def test_la_surcouche_remplace_les_textes(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    surcouche_en(racine)
    fr, en = charger(racine), charger(racine, "en")
    assert fr.concepts["intervalle"].titre == "Intervalle"  # le français ne bouge pas
    assert en.concepts["intervalle"].titre == "Interval"
    assert en.questions["intervalle-q1"].enonce == "How many steps in a third?"
    assert en.questions["intervalle-q3"] == fr.questions["intervalle-q3"]  # non traduite
    assert en.cartes["harmonie-demo"].titre == "Harmony demo"
    assert en.canonique("intervalles") == "intervalle"
    assert {"concepts/intervalle", "questions/intervalle-q1", "cartes/harmonie-demo"} <= en.traduits
    reste = manquants(en, ["harmonie-demo"])
    assert "concepts/intervalle" not in reste and "questions/intervalle-q3" in reste
    assert "concepts/accord-parfait" in reste and "quetes/entendre-une-cadence" in reste


@pytest.mark.parametrize(
    ("chemin", "avant", "apres", "message"),
    [
        ("concepts/intervalle.md", "domaine: musique", "domaine: finance", "domaine"),
        ("concepts/intervalle.md", "alias: [intervalles]", "alias: []", "alias"),
        ("questions/intervalle/intervalle-q1.md", "difficulte: 2", "difficulte: 5", "difficulte"),
        ("cartes/harmonie-demo.md", "quetes: [entendre-une-cadence]", "quetes: []", "quetes"),
    ],
)
def test_structure_differente_refusee(
    tmp_path: Path, chemin: str, avant: str, apres: str, message: str
) -> None:
    racine = copie_demo(tmp_path)
    fichier = surcouche_en(racine) / chemin
    fichier.write_text(
        fichier.read_text(encoding="utf-8").replace(avant, apres, 1), encoding="utf-8"
    )
    with pytest.raises(ErreurContenu, match=message):
        charger(racine, "en")


def test_traduction_d_un_concept_inconnu_refusee(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    ecrire(
        racine / "en" / "concepts" / "fantome.md",
        "---\ntype: concept\nid: fantome\ntitre: Ghost\ndomaine: musique\n---\n\n## Leçon\n\nx\n",
    )
    with pytest.raises(ErreurContenu, match="absent de la bibliothèque française"):
        charger(racine, "en")


def test_fichier_egare_dans_en_refuse(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    ecrire(racine / "en" / "notes.md", "x\n")
    with pytest.raises(ErreurContenu, match="hors de"):
        charger(racine)


def test_langue_inconnue(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="langue inconnue"):
        charger(copie_demo(tmp_path), "de")
