from dataclasses import fields

import pytest

from freinet.contenu import Carte, nom_par_defaut
from freinet.libelles_espace import ESPACE_EN, ESPACE_FR, libelles_espace


def test_les_deux_tables_ont_la_meme_forme() -> None:
    for champ in fields(ESPACE_FR):
        fr, en = getattr(ESPACE_FR, champ.name), getattr(ESPACE_EN, champ.name)
        assert type(fr) is type(en) and fr and en, champ.name
        if isinstance(fr, dict):
            assert set(fr) == set(en), champ.name
        if isinstance(fr, tuple):
            assert len(fr) == len(en), champ.name


def test_le_francais_d_avant() -> None:
    assert ESPACE_FR.onglets == ("Aujourd'hui", "Ma carte", "Cours")
    assert ESPACE_FR.notes == {1: "Raté", 2: "Difficile", 3: "Bien", 4: "Facile"}
    assert ESPACE_FR.etats["verrouille"] == "à venir" and ESPACE_FR.separateur == " : "


def test_choix_de_la_table() -> None:
    assert libelles_espace("fr") is ESPACE_FR and libelles_espace("en") is ESPACE_EN
    with pytest.raises(ValueError, match="langue inconnue"):
        libelles_espace("de")


def test_nom_de_carte() -> None:
    assert nom_par_defaut("trading-journalier") == "Trading journalier"
    carte = Carte("trading-journalier", ("a",), (), (), ())
    assert carte.nom == "Trading journalier"
    assert Carte("trading-journalier", ("a",), (), (), (), "Day trading").nom == "Day trading"
