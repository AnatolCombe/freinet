import sqlite3
from pathlib import Path

import pytest

from freinet.base import Base
from freinet.constantes import lire_regles
from freinet.etat import recalculer
from freinet.sauvegarde import (
    ErreurSauvegarde,
    nom_sauvegarde,
    restauration_valide,
    sauvegarder,
)
from tests.socle.fabrique import T0, revue

REGLES = lire_regles()


def _base_peuplee(chemin: Path) -> Base:
    base = Base(chemin)
    b = base.ajouter_brainiac("marius", "Europe/Paris")
    for i, jour in enumerate([0, 2, 13]):
        base.ajouter_revue(revue(f"r{i}", brainiac_id=b, nature="transfert", jour=jour))
    recalculer(base, b, REGLES)
    return base


def test_nom_horodate_en_utc() -> None:
    assert nom_sauvegarde(T0) == "freinet-20260101T070000Z.db"
    with pytest.raises(ValueError, match="sans fuseau"):
        nom_sauvegarde(T0.replace(tzinfo=None))


def test_sauvegarde_puis_restauration_rejoue_a_l_identique(tmp_path: Path) -> None:
    with _base_peuplee(tmp_path / "freinet.db") as base:
        copie = sauvegarder(base, tmp_path / "sauvegardes", T0)
    assert sorted(p.name for p in copie.parent.iterdir()) == [copie.name]
    avant = copie.read_bytes()
    assert restauration_valide(copie, REGLES)
    assert copie.read_bytes() == avant
    assert sorted(p.name for p in copie.parent.iterdir()) == [copie.name]


def test_sauvegarde_existante_jamais_ecrasee(tmp_path: Path) -> None:
    with _base_peuplee(tmp_path / "freinet.db") as base:
        sauvegarder(base, tmp_path / "s", T0)
        with pytest.raises(ErreurSauvegarde, match="existe déjà"):
            sauvegarder(base, tmp_path / "s", T0)


def test_base_corrompue_jamais_sauvegardee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _base_peuplee(tmp_path / "freinet.db") as base:
        monkeypatch.setattr(base, "integre", lambda: False)
        with pytest.raises(ErreurSauvegarde, match="integrity_check"):
            sauvegarder(base, tmp_path / "s", T0)
    assert not (tmp_path / "s").exists()


def test_restauration_detecte_des_caches_divergents(tmp_path: Path) -> None:
    with _base_peuplee(tmp_path / "freinet.db") as base:
        copie = sauvegarder(base, tmp_path / "s", T0)
    brut = sqlite3.connect(copie)
    with brut:
        brut.execute("UPDATE maitrise SET nb_revues = 99")
    brut.close()
    assert not restauration_valide(copie, REGLES)


def test_restauration_refuse_un_chemin_absent(tmp_path: Path) -> None:
    absent = tmp_path / "jamais-ecrite.db"
    assert not restauration_valide(absent, REGLES)
    assert not absent.exists()


def test_restauration_refuse_un_fichier_illisible(tmp_path: Path) -> None:
    faux = tmp_path / "faux.db"
    faux.write_bytes(b"pas une base sqlite" * 100)
    assert not restauration_valide(faux, REGLES)


def test_restauration_refuse_une_base_sans_eleve(tmp_path: Path) -> None:
    with Base(tmp_path / "vide.db") as base:
        copie = sauvegarder(base, tmp_path / "s", T0)
    assert not restauration_valide(copie, REGLES)
