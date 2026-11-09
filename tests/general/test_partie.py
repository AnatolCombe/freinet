from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from freinet.general import TYPES_ENIGME, ConfigGeneral, Listes
from freinet.partie_generale import TYPE_PAR_JOUR, bloc_du_jour, partie_du_jour
from tests.general.listes import ORIGINE, charger, ecrire_general

Donnees = tuple[ConfigGeneral, Listes]


@pytest.fixture(scope="module")
def donnees(tmp_path_factory: pytest.TempPathFactory) -> Donnees:
    return charger(ecrire_general(tmp_path_factory.mktemp("general")))


def test_general_meme_bloc_pour_tous(donnees: Donnees) -> None:
    CONFIG, LISTES = donnees
    jour = date(2026, 9, 30)
    marius = partie_du_jour("marius", jour, CONFIG, LISTES, None)
    noor = partie_du_jour("noor", jour, CONFIG, LISTES, None)
    assert marius.bloc == noor.bloc
    assert (marius.prenom, marius.mot_de) == ("MARIUS", None)
    assert (noor.prenom, noor.mot_de) == ("NOOR", "Camille")
    assert marius.ville == "Lyon" and marius.meteo is None


def test_rotation_des_langues(donnees: Donnees) -> None:
    CONFIG, LISTES = donnees
    mots = [bloc_du_jour(ORIGINE + timedelta(n), CONFIG, LISTES).mot.id for n in range(11)]
    assert mots == [
        "dor",
        "waldeinsamkeit",
        "apricity",
        "sobremesa",
        "firgun",
        "omenie",
        "waldeinsamkeit",
        "apricity",
        "sobremesa",
        "firgun",
        "dor",
    ]


def test_enigme_suit_le_jour_de_la_semaine(donnees: Donnees) -> None:
    CONFIG, LISTES = donnees
    logiques = [
        bloc_du_jour(ORIGINE + timedelta(n), CONFIG, LISTES).enigme.id for n in (0, 3, 6, 7)
    ]
    assert logiques == ["logique-1", "logique-2", "logique-1", "logique-2"]
    assert bloc_du_jour(date(2026, 1, 6), CONFIG, LISTES).enigme.id == "mots-1"  # mardi


def test_avant_l_origine_et_29_fevrier(donnees: Donnees) -> None:
    CONFIG, LISTES = donnees
    veille = bloc_du_jour(ORIGINE - timedelta(1), CONFIG, LISTES)  # dimanche 4 janvier
    assert (veille.mot.id, veille.enigme.id) == ("firgun", "logique-2")
    assert bloc_du_jour(date(2028, 2, 29), CONFIG, LISTES).fait.jour == "02-29"
    assert bloc_du_jour(date(2026, 9, 30), CONFIG, LISTES).fait.annee == 1791


@given(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
def test_bloc_fonction_de_la_date(donnees: Donnees, jour: date) -> None:
    CONFIG, LISTES = donnees
    bloc = bloc_du_jour(jour, CONFIG, LISTES)
    assert bloc == bloc_du_jour(jour, CONFIG, LISTES)  # inv. 6
    assert bloc.enigme.type == TYPE_PAR_JOUR[jour.weekday()]
    assert bloc.mot.langue == CONFIG.langues[(jour - ORIGINE).days % len(CONFIG.langues)]
    assert bloc.fait.jour == f"{jour:%m-%d}"


def test_chaque_jour_a_un_type_d_enigme_connu() -> None:
    assert set(TYPE_PAR_JOUR) == set(TYPES_ENIGME)  # sinon % 0 certains jours


def test_le_jour_de_l_anglais_est_celui_du_francais(tmp_path: Path) -> None:
    dossier = ecrire_general(tmp_path, en=True)
    config, listes_fr = charger(dossier)
    _, listes_en = charger(dossier, "en")
    mercredi = date(2026, 1, 7)  # rang 2 depuis l'origine : anglais / français
    marius = partie_du_jour("marius", mercredi, config, listes_fr, None)
    noor = partie_du_jour("noor", mercredi, config, listes_en, None)
    assert (marius.bloc.mot.id, noor.bloc.mot.id) == ("apricity", "flaner")
    assert (marius.langue, noor.langue) == ("fr", "en")
    assert noor.bloc.fait.texte == "Fact of 07/01."
