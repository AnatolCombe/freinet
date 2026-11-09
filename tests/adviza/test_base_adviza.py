import sqlite3
from pathlib import Path

import pytest

from freinet.base import Base


def test_requetes_en_ajout_seul_et_par_eleve(tmp_path: Path) -> None:
    chemin = tmp_path / "freinet.db"
    with Base(chemin) as base:
        marius = base.ajouter_brainiac("marius", "Europe/Paris")
        lina = base.ajouter_brainiac("lina", "Europe/Paris")
        assert base.requete_adviza(marius, "k") is None
        assert base.enregistrer_requete_adviza(marius, "k", "noter", "e1", '{"statut": 200}')
        assert not base.enregistrer_requete_adviza(marius, "k", "noter", "e2", "{}")
        assert base.requete_adviza(marius, "k") == ("noter", "e1", '{"statut": 200}')
        assert base.requete_adviza(lina, "k") is None  # une clé appartient à un élève
        assert base.enregistrer_requete_adviza(lina, "k", "joker", "e3", "{}")
        assert base.requete_adviza(marius, "k") == ("noter", "e1", '{"statut": 200}')
    brut = sqlite3.connect(chemin)
    try:
        for sql in (
            "UPDATE adviza_requete SET reponse = 'x'",
            "DELETE FROM adviza_requete",
            "INSERT OR REPLACE INTO adviza_requete SELECT * FROM adviza_requete",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="ajout seul"):
                brut.execute(sql)
    finally:
        brut.close()


def test_enregistrement_refuse_annule_la_transaction(tmp_path: Path) -> None:
    with Base(tmp_path / "freinet.db") as base:
        marius = base.ajouter_brainiac("marius", "Europe/Paris")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            base.enregistrer_requete_adviza("eleve-inconnu", "k", "noter", "e", "{}")
        assert base.enregistrer_requete_adviza(marius, "k", "noter", "e", "{}")  # verrou rendu
        assert base.requete_adviza("eleve-inconnu", "k") is None
