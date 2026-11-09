import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from freinet.bibliotheque import charger
from freinet.index import generer_index
from tests.bibliotheque.demo import DEMO, copie_demo, ecrire

RACINE = Path(__file__).resolve().parents[2]


def test_index_de_demo() -> None:
    texte = generer_index(charger(DEMO))
    assert "| harmonie-demo | 4 | entendre-une-cadence |" in texte
    assert "| intervalle | Intervalle | musique | harmonie-demo |" in texte
    assert texte == generer_index(charger(DEMO))


def test_index_vide(tmp_path: Path) -> None:
    assert generer_index(charger(tmp_path)).endswith("Vide : aucune carte publiée.\n")


def test_index_du_depot_a_jour() -> None:
    # inv. 13 : l'index versionné est exactement ce que génère le script.
    resultat = subprocess.run(
        [sys.executable, str(RACINE / "scripts" / "regen-index.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultat.returncode == 0, resultat.stderr


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "regen_index", RACINE / "scripts" / "regen-index.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_index_absent_ou_perime(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    copie_demo(tmp_path)
    script = _script()
    assert script.main(["--check"], tmp_path) == 1
    assert "n'est pas à jour" in capsys.readouterr().err
    assert script.main([], tmp_path) == 0
    assert script.main(["--check"], tmp_path) == 0


def test_bibliotheque_invalide_refusee(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = copie_demo(tmp_path)
    ecrire(racine / "concepts" / "casse.md", "pas de frontmatter\n")
    assert _script().main([], tmp_path) == 1
    assert "bibliothèque invalide" in capsys.readouterr().err
    assert not (racine / "index.md").exists()


def test_barre_verticale_echappee(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    fichier = racine / "concepts" / "intervalle.md"
    fichier.write_text(
        fichier.read_text(encoding="utf-8").replace("titre: Intervalle", "titre: Do | Mi"),
        encoding="utf-8",
    )
    assert "| intervalle | Do \\| Mi | musique |" in generer_index(charger(racine))
