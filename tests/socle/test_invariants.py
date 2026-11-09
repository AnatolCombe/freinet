"""Invariants 1, 3 et 10 du PRD §4. Les tests ont le droit d'importer sqlite3 : pas le code."""

import re
import sqlite3
from pathlib import Path

import pytest

from freinet.base import Base
from tests.socle.fabrique import revue

RACINE = Path(__file__).resolve().parents[2]
_IMPORT_SQLITE = re.compile(r"^\s*(import sqlite3|from sqlite3 import)", re.MULTILINE)
_SQL = re.compile(r"\.(execute|executescript|executemany)\(|\b(SELECT|INSERT|UPDATE|DELETE)\s")
COUCHE = RACINE / "freinet" / "base"


def _code() -> list[Path]:
    return [
        f
        for f in RACINE.rglob("*.py")
        if not f.is_relative_to(RACINE / "tests")
        and not any(partie.startswith(".") for partie in f.relative_to(RACINE).parts)
    ]


def test_un_seul_module_base() -> None:
    """Inv. 1 : une seule couche parle à la base, le paquet `freinet/base/` — aucun autre
    fichier n'importe sqlite3 ni n'exécute de SQL."""
    importe = {f for f in _code() if _IMPORT_SQLITE.search(f.read_text(encoding="utf-8"))}
    assert importe and all(f.is_relative_to(COUCHE) for f in importe)
    dehors = [
        f.relative_to(RACINE).as_posix()
        for f in _code()
        if not f.is_relative_to(COUCHE) and _SQL.search(f.read_text(encoding="utf-8"))
    ]
    assert dehors == []


def test_revue_append_only(tmp_path: Path) -> None:
    chemin = tmp_path / "freinet.db"
    with Base(chemin) as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        base.ajouter_revue(revue("r1", brainiac_id=b))
    brut = sqlite3.connect(chemin)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="ajout seul"):
            brut.execute("UPDATE revue SET note = 1")
        with pytest.raises(sqlite3.IntegrityError, match="ajout seul"):
            brut.execute("DELETE FROM revue")
        with pytest.raises(sqlite3.IntegrityError, match="ajout seul"):
            brut.execute("INSERT OR REPLACE INTO revue SELECT * FROM revue")
    finally:
        brut.close()


def test_schema_multi_brainiac() -> None:
    with Base(":memory:") as base:
        tables_etat = [t for t in base.tables() if t != "schema_version"]
        assert tables_etat
        sans = [t for t in tables_etat if "brainiac_id" not in base.colonnes(t)]
        assert sans == []
