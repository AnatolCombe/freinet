import shutil
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from freinet import eleves, imprimante, quotidien, rendu
from freinet.base import Base
from freinet.imprimante import INITIALISER
from tests.bibliotheque.demo import DEMO, surcouche_en
from tests.ticket.fausse_imprimante import Etat, fausse_imprimante, port_ferme

LUNDI = "2026-01-05T05:00:00+00:00"


def _racine(tmp_path: Path) -> Path:
    shutil.copytree(DEMO, tmp_path / "bibliotheque")
    assert eleves.main(["--racine", str(tmp_path), "ajouter", "marius", "Europe/Paris"]) == 0
    assert eleves.main(["--racine", str(tmp_path), "inscrire", "marius", "harmonie-demo"]) == 0
    arguments = ["--racine", str(tmp_path), "--eleve", "marius", "--instant", LUNDI]
    assert quotidien.main(arguments) == 0
    return tmp_path


def _rendu(racine: Path, *options: str) -> int:
    return rendu.main(
        ["--racine", str(racine), "--eleve", "marius", "--jour", "2026-01-05", *options]
    )


def _presentes(racine: Path) -> dict[str, date]:
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom("marius")
        assert eleve is not None
        return base.concepts_presentes(eleve.brainiac_id, avant=date(2026, 1, 6))


def _sortie(racine: Path) -> Path:
    return racine / "quotidien" / "03_rendu" / "output" / "marius"


def test_rendu_sans_imprimer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = _racine(tmp_path)
    assert _rendu(racine) == 0
    png = _sortie(racine) / "ticket-2026-01-05.png"
    assert capsys.readouterr().out.splitlines()[-1] == str(png)
    with Image.open(png) as image:
        assert image.width == 576
    texte = png.with_suffix(".txt").read_text("utf-8")
    assert texte.startswith("FREINET · MARIUS\nlundi 5 janvier 2026\n")  # prénom en tête (PROF-8)
    assert sorted(p.name for p in _sortie(racine).iterdir()) == [
        "acces-2026-01-05.txt",  # jeton et code en clair, fichier privé (0600)
        "ticket-2026-01-05.png",
        "ticket-2026-01-05.txt",
    ]
    assert (_sortie(racine) / "acces-2026-01-05.txt").stat().st_mode & 0o777 == 0o600
    assert _presentes(racine) == {}  # pas imprimé : la notion n'est pas encore présentée


def test_impression(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = _racine(tmp_path)
    with fausse_imprimante() as fausse:
        assert _rendu(racine, "--imprimante", f"127.0.0.1:{fausse.port}") == 0
    assert "(imprimé)" in capsys.readouterr().out
    assert len(fausse.recus) == 1 and fausse.recus[0].startswith(INITIALISER)
    assert _presentes(racine) == {"intervalle": date(2026, 1, 5)}


def test_impression_depuis_la_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = _racine(tmp_path)
    config = tmp_path / "imprimante.md"
    monkeypatch.setattr(imprimante, "FICHIER_IMPRIMANTE", config)  # jamais la vraie imprimante
    with fausse_imprimante() as fausse:
        config.write_text(f"| IP | 127.0.0.1 |\n| Port | {fausse.port} |\n", encoding="utf-8")
        assert _rendu(racine, "--imprimer") == 0
    assert len(fausse.recus) == 1
    config.write_text("| IP | à renseigner |\n", encoding="utf-8")
    assert _rendu(racine, "--imprimer") == 1
    assert "à renseigner" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("etat", "port", "message"),
    [
        (None, "ferme", "impression non confirmée"),
        (Etat(papier=0x72), None, "plus de papier"),
    ],
)
def test_impression_non_confirmee(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    etat: Etat | None,
    port: str | None,
    message: str,
) -> None:
    racine = _racine(tmp_path)
    with fausse_imprimante(etat) as fausse:
        cible = port_ferme() if port == "ferme" else fausse.port
        assert _rendu(racine, "--imprimante", f"127.0.0.1:{cible}") == 3
    assert message in capsys.readouterr().err
    assert (_sortie(racine) / "ticket-2026-01-05.png").is_file()  # repli : le ticket reste
    assert _presentes(racine) == {}  # rien n'est sorti : la notion reviendra


def test_remis_sans_imprimer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = _racine(tmp_path)
    assert _rendu(racine, "--remis") == 0
    assert capsys.readouterr().out.splitlines()[-1].endswith("(remis)")
    assert _presentes(racine) == {"intervalle": date(2026, 1, 5)}


@pytest.mark.parametrize(
    ("options", "message"),
    [(["--jour", "2026-01-06"], "aucun plan le 2026-01-06")],
)
def test_rendu_impossible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], options: list[str], message: str
) -> None:
    racine = _racine(tmp_path)
    assert _rendu(racine, *options) == 1
    assert message in capsys.readouterr().err


def test_eleve_inconnu(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = _racine(tmp_path)
    assert rendu.main(["--racine", str(racine), "--eleve", "personne"]) == 1
    assert "élève inconnu" in capsys.readouterr().err


def test_rendu_dans_la_langue_du_plan(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    surcouche_en(racine / "bibliotheque")
    plan = racine / "brainiacs" / "marius" / "plans" / "2026-01-05.md"
    plan.write_text(  # un plan retouché à la main : le plan fait foi
        "---\ntype: plan\njour: '2026-01-05'\nlangue: en\nitems:\n"
        "- {question_id: intervalle-q1, concept_id: intervalle, nature: rappel}\n---\n\n"
        "# Plan du 2026-01-05\n\n## Review\n\n1. How many steps in a third?\n",
        encoding="utf-8",
    )
    assert _rendu(racine, "--sans-qr") == 0
    texte = (_sortie(racine) / "ticket-2026-01-05.txt").read_text("utf-8")
    assert "1. Three." in texte and "Trois." not in texte and "ANSWERS" in texte
