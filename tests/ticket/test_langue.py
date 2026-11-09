from dataclasses import fields
from datetime import date

import pytest

from freinet.imprimable import absents
from freinet.langue import EN, FR, LANGUES, libelles


def test_les_deux_tables_ont_la_meme_forme() -> None:
    for champ in fields(FR):
        fr, en = getattr(FR, champ.name), getattr(EN, champ.name)
        assert type(fr) is type(en), champ.name
        if isinstance(fr, tuple):
            assert len(fr) == len(en), champ.name
        if isinstance(fr, dict):
            assert set(fr) == set(en), champ.name
        assert fr and en, champ.name


def test_tout_est_imprimable() -> None:
    for table in (FR, EN):
        for champ in fields(table):
            valeur = getattr(table, champ.name)
            textes = (
                list(valeur.values()) if isinstance(valeur, dict)
                else list(valeur) if isinstance(valeur, tuple) else [valeur]
            )  # fmt: skip
            for texte in textes:
                assert not absents(texte), (table.code, champ.name, texte)


def test_dates() -> None:
    mardi = date(2026, 1, 6)
    assert FR.date_longue(mardi) == "mardi 6 janvier 2026"
    assert EN.date_longue(mardi) == "Tuesday 6 January 2026"
    assert FR.jour_du_mois(date(2026, 10, 1)) == "1er octobre"
    assert EN.jour_du_mois(date(2026, 10, 1)) == "1 October"
    assert (FR.annee(-44), EN.annee(-44), EN.annee(1869)) == ("44 av. J.-C.", "44 BC", "1869")
    assert (FR.heure("07:42"), EN.heure("07:42")) == ("7 h 42", "7:42")


def test_choix_de_la_table() -> None:
    assert LANGUES == ("fr", "en")
    assert libelles("fr") is FR and libelles("en") is EN
    with pytest.raises(ValueError, match="langue inconnue"):
        libelles("de")


def test_les_defis_gardent_leur_gabarit() -> None:
    assert all("{titre}" in d for d in (*FR.defis, *EN.defis))
