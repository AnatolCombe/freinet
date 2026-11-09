import shutil
import threading
from datetime import date
from pathlib import Path

import pytest

from freinet import matin, quotidien, verrou
from freinet.base import Base
from tests.matin.scenario import LUNDI_6H, configurer, racine_matin
from tests.ticket.fausse_imprimante import Etat, fausse_imprimante


def _statuts(racine: Path) -> dict[str, str | None]:
    with Base(racine / "data" / "freinet.db") as base:
        eleves = [base.brainiac(b) for b in base.brainiacs()]
        return {e.nom: base.statut_du_plan(e.brainiac_id, date(2026, 1, 5)) for e in eleves if e}


def test_tous_les_eleves_puis_rien_en_double(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = racine_matin(tmp_path / "r")
    with fausse_imprimante() as fausse:
        configurer(monkeypatch, tmp_path, fausse.port)
        assert matin.main(["--racine", str(racine), "--instant", LUNDI_6H]) == 0
        assert len(fausse.recus) == 2
        assert matin.main(["--racine", str(racine), "--instant", LUNDI_6H]) == 0  # réveil tardif
        assert len(fausse.recus) == 2  # rattrapage sans doublon
    assert _statuts(racine) == {"alice": "imprime", "marius": "imprime"}
    sortie = capsys.readouterr().out
    assert "alice : remis" in sortie and "marius : déjà remis" in sortie


def test_imprimante_en_panne_code_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = racine_matin(tmp_path / "r", ("marius",))
    with fausse_imprimante(Etat(papier=0x72)) as fausse:
        configurer(monkeypatch, tmp_path, fausse.port)
        assert matin.main(["--racine", str(racine), "--instant", LUNDI_6H]) == 3
    assert "marius : non imprimé" in capsys.readouterr().err
    assert _statuts(racine) == {"marius": "planifie"}  # plan et PNG gardés


def test_imprimante_non_configuree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = racine_matin(tmp_path / "r", ("marius",))
    configurer(monkeypatch, tmp_path, None)
    assert matin.main(["--racine", str(racine), "--instant", LUNDI_6H]) == 3
    erreurs = capsys.readouterr().err
    assert "sans imprimante" in erreurs and "marius : non imprimé" in erreurs


def test_un_eleve_en_erreur_n_arrete_pas_les_autres(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = racine_matin(tmp_path / "r")
    configurer(monkeypatch, tmp_path, None)
    arguments = ["--racine", str(racine), "--instant", LUNDI_6H, "--sans-imprimante"]
    assert matin.main([*arguments, "--eleve", "inconnu", "--eleve", "marius"]) == 1
    erreurs = capsys.readouterr().err
    assert "inconnu : erreur" in erreurs and "marius : non imprimé" in erreurs


def test_sans_eleve_ou_sans_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configurer(monkeypatch, tmp_path, None)
    shutil.copytree(
        racine_matin(tmp_path / "r", ()) / "bibliotheque", tmp_path / "vide" / "bibliotheque"
    )
    assert matin.main(["--racine", str(tmp_path / "vide"), "--instant", LUNDI_6H]) == 1
    (tmp_path / "retour.md").write_text("| Port | 0 |\n", encoding="utf-8")
    assert matin.main(["--racine", str(tmp_path / "r"), "--instant", LUNDI_6H]) == 1


def test_codes_de_sortie() -> None:
    r = matin.Resultat
    assert matin.code_de_sortie([r("a", "remis", ""), r("b", "déjà remis", "")]) == 0
    assert matin.code_de_sortie([r("a", "remis", ""), r("b", "non imprimé", "")]) == 3
    assert matin.code_de_sortie([r("a", "non imprimé", ""), r("b", "erreur", "")]) == 1


def test_deux_matins_simultanes_un_seul_ticket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = racine_matin(tmp_path / "r")
    codes: list[int] = []
    with fausse_imprimante() as fausse:
        configurer(monkeypatch, tmp_path, fausse.port)
        arguments = ["--racine", str(racine), "--instant", LUNDI_6H]
        fils = [
            threading.Thread(target=lambda: codes.append(matin.main(arguments))) for _ in range(2)
        ]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
    assert codes == [0, 0] and len(fausse.recus) == 2  # un ticket par élève, pas quatre


def test_un_bogue_chez_un_eleve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = racine_matin(tmp_path / "r")
    configurer(monkeypatch, tmp_path, None)
    vrai = quotidien.preparer_jour

    def preparer(racine: Path, nom: str, *reste: object) -> Path:
        if nom == "alice":
            raise KeyError("bogue")
        return vrai(racine, nom, *reste)  # type: ignore[arg-type]

    monkeypatch.setattr(matin, "preparer_jour", preparer)
    arguments = ["--racine", str(racine), "--instant", LUNDI_6H, "--sans-imprimante"]
    assert matin.main(arguments) == 1
    erreurs = capsys.readouterr().err
    assert "alice : erreur — bogue : KeyError" in erreurs and "marius : non imprimé" in erreurs


def test_rituel_deja_en_cours(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = racine_matin(tmp_path / "r", ("marius",))
    configurer(monkeypatch, tmp_path, None)
    monkeypatch.setattr(verrou, "ATTENTE_S", 0.3)
    monkeypatch.setattr(matin, "verrou_du_rituel", lambda r: verrou.verrou_du_rituel(r, 0.3))
    with verrou.verrou_du_rituel(racine):
        assert matin.main(["--racine", str(racine), "--instant", LUNDI_6H]) == 1
    assert "un autre rituel est en cours" in capsys.readouterr().err
