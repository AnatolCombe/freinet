from pathlib import Path

import pytest

from freinet.bibliotheque import charger
from freinet.recherche import candidats, main, rapport
from tests.bibliotheque.demo import DEMO

BIB = charger(DEMO)


def test_trouve_le_concept_existant_malgre_accents_et_pluriel() -> None:
    trouves = candidats(BIB, "Accords parfaits", "musique")
    assert trouves[0].id == "accord-parfait"
    assert not trouves[0].autre_domaine
    assert len(trouves) <= 5


def test_domaine_compare_sans_casse_ni_espaces() -> None:
    assert not candidats(BIB, "accord parfait", " Musique ")[0].autre_domaine


def test_homonyme_d_un_autre_domaine_signale() -> None:
    trouves = candidats(BIB, "intervalle de confiance", "statistique")
    assert trouves[0].id == "intervalle"
    assert trouves[0].autre_domaine
    assert [c.id for c in trouves] == ["intervalle"]
    assert "autre domaine : ne pas fusionner" in rapport(
        "intervalle de confiance", "statistique", trouves
    )


def test_syntaxe_fts_de_l_appelant_neutralisee() -> None:
    assert candidats(BIB, 'NEAR( "accord" OR *', "musique")[0].id == "accord-parfait"
    assert candidats(BIB, "\" ( ) l'", "musique") == []


def test_rien_de_proche() -> None:
    assert candidats(BIB, "photosynthèse", "biologie") == []
    assert candidats(BIB, "la photosynthèse des plantes", "biologie") == []
    assert candidats(BIB, "l'effet de levier", "finance") == []
    assert "créer un nouveau concept" in rapport("photosynthèse", "biologie", [])


def test_ligne_de_commande(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["cadence", "--domaine", "musique", "--bibliotheque", str(DEMO)])
    assert code == 0
    assert "cadence-parfaite — Cadence parfaite (musique)" in capsys.readouterr().out


def test_bibliotheque_illisible_message_clair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["cadence", "--domaine", "musique", "--bibliotheque", str(tmp_path / "absente")]) == 2
    )
    assert "bibliothèque illisible" in capsys.readouterr().err
