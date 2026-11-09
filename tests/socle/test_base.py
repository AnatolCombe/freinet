import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import pytest

from freinet.base import Base
from freinet.modele import EtatConcept, Revue
from tests.socle.fabrique import T0, revue


def test_migration_cree_les_tables(tmp_path: Path) -> None:
    with Base(tmp_path / "data" / "freinet.db") as base:
        assert {"brainiac", "inscription", "plan_du_jour", "revue", "fsrs", "maitrise"} <= set(
            base.tables()
        )


def test_migration_idempotente(tmp_path: Path) -> None:
    chemin = tmp_path / "freinet.db"
    with Base(chemin) as base:
        brainiac_id = base.ajouter_brainiac("marius", "Europe/Paris")
    with Base(chemin) as base:
        assert base.brainiacs() == [brainiac_id]


def test_colonnes_table_inconnue_refusee() -> None:
    with Base(":memory:") as base, pytest.raises(ValueError, match="table inconnue"):
        base.colonnes("inexistante")


def test_revue_aller_retour() -> None:
    with Base(":memory:") as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        r = revue("r1", brainiac_id=b, nature="transfert", note=4, jour=2.5, saisi_jour=3)
        base.ajouter_revue(r)
        assert base.revues(b) == [r]


def test_etat_aller_retour_et_remplacement() -> None:
    with Base(":memory:") as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        e1 = EtatConcept(b, "c1", '{"x": 1}', 2, None)
        e2 = EtatConcept(b, "c2", '{"x": 2}', 5, T0)
        base.remplacer_etat(b, lambda _revues: [e1, e2])
        assert base.etat(b) == [e1, e2]
        base.remplacer_etat(b, lambda _revues: [e2])
        assert base.etat(b) == [e2]


def test_etat_d_un_autre_eleve_refuse_et_caches_intacts() -> None:
    with Base(":memory:") as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        avant = EtatConcept(b, "c1", '{"x": 1}', 2, None)
        base.remplacer_etat(b, lambda _revues: [avant])
        with pytest.raises(ValueError, match="écrit pour"):
            base.remplacer_etat(b, lambda _revues: [EtatConcept("autre", "c1", "{}", 1, None)])
        assert base.etat(b) == [avant]


def test_correction_ne_traverse_pas_les_eleves() -> None:
    with Base(":memory:") as base:
        a = base.ajouter_brainiac("marius", "Europe/Paris")
        b = base.ajouter_brainiac("ami", "Europe/Paris")
        base.ajouter_revue(revue("r1", brainiac_id=a))
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            base.ajouter_revue(revue("r2", brainiac_id=b, corrige_id="r1"))
        base.ajouter_revue(revue("r3", brainiac_id=a, corrige_id="r1"))


def test_ouvertures_concurrentes_migrent_une_seule_fois(tmp_path: Path) -> None:
    # Page QR et passage quotidien peuvent ouvrir une base neuve au même instant.
    for essai in range(10):
        chemin = tmp_path / f"freinet-{essai}.db"

        def ouvrir(_: int, chemin: Path = chemin) -> list[str]:
            with Base(chemin) as base:
                return base.tables()

        with ThreadPoolExecutor(max_workers=6) as groupe:
            resultats = list(groupe.map(ouvrir, range(6)))
        assert all("revue" in tables for tables in resultats)


def test_migration_en_echec_ne_laisse_rien(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_casse.sql").write_text(
        "CREATE TABLE partielle (a INTEGER);\nCREATE TABLE casse (;\n", encoding="utf-8"
    )
    monkeypatch.setattr("freinet.base.MIGRATIONS", migrations)
    chemin = tmp_path / "freinet.db"
    with pytest.raises(sqlite3.OperationalError):
        Base(chemin)
    brut = sqlite3.connect(chemin)
    try:
        tables = {nom for (nom,) in brut.execute("SELECT name FROM sqlite_master")}
        versions = brut.execute("SELECT count(*) FROM schema_version").fetchone()
    finally:
        brut.close()
    assert "partielle" not in tables
    assert versions == (0,)


def test_recalcul_sous_verrou_bloque_les_autres_ecritures(tmp_path: Path) -> None:
    chemin = tmp_path / "freinet.db"
    with Base(chemin) as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")

        def calcul(_revues: list[Revue]) -> list[EtatConcept]:
            autre = sqlite3.connect(chemin, timeout=0.1)
            try:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    autre.execute(
                        "INSERT INTO brainiac (brainiac_id, nom, fuseau, cree_le)"
                        " VALUES ('x', 'ami', 'UTC', '2026-01-01T00:00:00+00:00')"
                    )
            finally:
                autre.close()
            return []

        assert base.remplacer_etat(b, calcul) == []


def test_eleve_inscription_et_plan_du_jour() -> None:
    with Base(":memory:") as base:
        assert base.brainiac_par_nom("marius") is None
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        eleve = base.brainiac_par_nom("marius")
        assert eleve is not None and (eleve.brainiac_id, eleve.dosage) == (b, (60, 25, 15))
        base.inscrire(b, "harmonie-demo", None)
        base.inscrire(b, "harmonie-demo", "entendre-une-cadence")
        assert [(i.carte_id, i.quete_active) for i in base.inscriptions(b)] == [
            ("harmonie-demo", "entendre-une-cadence")
        ]
        plan = base.plan_du_jour(b, date(2026, 1, 5), "intervalle")
        assert base.plan_du_jour(b, date(2026, 1, 5), "intervalle") == plan
        assert base.plan_du_jour(b, date(2026, 1, 5)) == plan  # relire n'efface pas la notion
        assert base.plan_du_jour(b, date(2026, 1, 6)) != plan
        base.plan_du_jour(b, date(2026, 1, 7), "intervalle")
        assert base.concepts_presentes(b, avant=date(2026, 1, 8)) == {}  # rien d'imprimé
        base.marquer_imprime(b, date(2026, 1, 5))
        base.marquer_imprime(b, date(2026, 1, 7))
        base.marquer_imprime(b, date(2026, 1, 9))  # pas de plan ce jour-là : sans effet
        assert base.concepts_presentes(b, avant=date(2026, 1, 6)) == {
            "intervalle": date(2026, 1, 5)
        }
        assert base.concepts_presentes(b, avant=date(2026, 1, 8)) == {
            "intervalle": date(2026, 1, 5)
        }
        assert base.concepts_presentes(b, avant=date(2026, 1, 5)) == {}
        assert base.fixer_plan(b, date(2026, 1, 5), None) == plan  # la base suit le fichier
        assert base.concepts_presentes(b, avant=date(2026, 1, 6)) == {}
        with pytest.raises(TypeError, match="jour logique"):
            base.plan_du_jour(b, datetime(2026, 1, 5))
        with pytest.raises(TypeError, match="jour logique"):
            base.concepts_presentes(b, avant=datetime(2026, 1, 6))
        with pytest.raises(TypeError, match="jour logique"):
            base.marquer_imprime(b, datetime(2026, 1, 6))
        base.inscrire(b, "harmonie-demo", None)  # réinscrire sans quête garde la quête
        assert base.inscriptions(b)[0].quete_active == "entendre-une-cadence"
