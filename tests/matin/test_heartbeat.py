import shutil
import socket
import subprocess
from datetime import date
from pathlib import Path

import pytest

from freinet import heartbeat, matin
from freinet.base import Base
from freinet.imprimante import Imprimante, etat_papier
from freinet.verrou import verrou_du_rituel
from tests.matin.scenario import LUNDI_6H, configurer, racine_matin
from tests.ticket.fausse_imprimante import Etat, fausse_imprimante, port_ferme

SEPT_HEURES = "2026-01-05T06:00:00+00:00"


@pytest.fixture
def notifications(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    recues: list[str] = []
    monkeypatch.setattr(heartbeat, "notifier", recues.append)
    return recues


def test_tout_va_bien(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notifications: list[str]
) -> None:
    racine = racine_matin(tmp_path / "r", ("marius",))
    with fausse_imprimante() as fausse:
        configurer(monkeypatch, tmp_path, fausse.port)
        assert matin.main(["--racine", str(racine), "--instant", LUNDI_6H]) == 0
        assert (
            heartbeat.main(["--racine", str(racine), "--instant", SEPT_HEURES, "--sans-page"]) == 0
        )
    assert notifications == []


def test_pas_de_ticket_et_papier_bientot_fini(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notifications: list[str]
) -> None:
    racine = racine_matin(tmp_path / "r")
    arguments = ["--racine", str(racine), "--instant", LUNDI_6H, "--eleve", "marius"]
    configurer(monkeypatch, tmp_path, None)
    assert matin.main([*arguments, "--sans-imprimante"]) == 3
    with fausse_imprimante(Etat(papier=0x1E)) as fausse:  # capteur « bientôt fini »
        configurer(monkeypatch, tmp_path, fausse.port)
        assert (
            heartbeat.main(["--racine", str(racine), "--instant", SEPT_HEURES, "--sans-page"]) == 1
        )
    assert notifications == [
        "alice : pas de ticket le 2026-01-05 (aucun plan)",
        "marius : pas de ticket le 2026-01-05 (plan prêt, non imprimé)",
        "papier : bientôt fini",
    ]


def test_imprimante_injoignable_ou_non_configuree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notifications: list[str]
) -> None:
    racine = racine_matin(tmp_path / "r", ("marius",))
    arguments = ["--racine", str(racine), "--instant", LUNDI_6H, "--sans-imprimante"]
    configurer(monkeypatch, tmp_path, None)
    assert matin.main([*arguments, "--eleve", "marius"]) == 3
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom("marius")
        assert eleve is not None
        base.marquer_imprime(eleve.brainiac_id, date(2026, 1, 5))
    configurer(monkeypatch, tmp_path, port_ferme())
    assert heartbeat.main(["--racine", str(racine), "--instant", SEPT_HEURES, "--sans-page"]) == 1
    assert notifications == [notifications[0]] and notifications[0].startswith(
        "imprimante injoignable"
    )
    configurer(monkeypatch, tmp_path, None)
    assert heartbeat.main(["--racine", str(racine), "--instant", SEPT_HEURES, "--sans-page"]) == 0
    arguments = ["--racine", str(tmp_path / "nulle-part"), "--sans-imprimante", "--sans-page"]
    assert heartbeat.main(arguments) == 1
    assert notifications[-1].startswith("base absente")


def test_etat_papier() -> None:
    with fausse_imprimante() as fausse:
        assert etat_papier(Imprimante("127.0.0.1", fausse.port)) == "ok"
    with fausse_imprimante(Etat(imprimante=0x1A, cause=0x16)) as fausse:
        assert etat_papier(Imprimante("127.0.0.1", fausse.port)) == "imprimante capot ouvert"


def test_notification_sans_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[list[str]] = []

    def enregistrer(commande: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        appels.append(commande)
        return subprocess.CompletedProcess(commande, 0)

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/osascript")
    monkeypatch.setattr(subprocess, "run", enregistrer)
    piege = '-e do shell script "rm -rf ~"'
    assert heartbeat.notifier(piege)
    assert appels[0][-1] == f"• {piege}"  # argument préfixé, jamais lu comme du script
    assert all(piege not in morceau for morceau in appels[0][:-1])


@pytest.mark.parametrize("echec", ["code", "delai", "absent"])
def test_notification_ratee(monkeypatch: pytest.MonkeyPatch, echec: str) -> None:
    def lancer(commande: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        if echec == "delai":
            raise subprocess.TimeoutExpired(commande, 10)
        return subprocess.CompletedProcess(commande, 1)

    osascript = None if echec == "absent" else "/usr/bin/osascript"
    monkeypatch.setattr(shutil, "which", lambda _: osascript)
    monkeypatch.setattr(subprocess, "run", lancer)
    assert heartbeat.notifier("alerte") is False


def test_essai_de_notification(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    envoyees: list[str] = []

    def enregistrer(message: str) -> bool:
        envoyees.append(message)
        return True

    monkeypatch.setattr(heartbeat, "notifier", enregistrer)
    assert heartbeat.main(["--essai"]) == 0 and "essai" in envoyees[0]
    monkeypatch.setattr(heartbeat, "notifier", lambda m: False)
    assert heartbeat.main(["--essai"]) == 1
    assert "refusée" in capsys.readouterr().out


def test_page_du_qr(tmp_path: Path) -> None:
    with socket.create_server(("127.0.0.1", 0)) as ecoute:
        assert heartbeat.page_injoignable(ecoute.getsockname()[1]) is None
    refus = heartbeat.page_injoignable(port_ferme())
    assert refus is not None and refus.startswith("page du QR injoignable")


def test_attend_la_fin_du_rituel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Réveil tardif : le heartbeat attend que le matin ait fini, sans fausse alerte."""
    racine = racine_matin(tmp_path / "r", ("marius",))
    configurer(monkeypatch, tmp_path, None)
    monkeypatch.setattr(heartbeat, "ATTENTE_RITUEL_S", 0.3)
    with verrou_du_rituel(racine):
        arguments = ["--racine", str(racine), "--instant", SEPT_HEURES, "--sans-page"]
        assert heartbeat.main(arguments) == 1  # le verrou ne se libère pas : alerte explicite


def test_aucun_eleve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notifications: list[str]
) -> None:
    racine = racine_matin(tmp_path / "r", ())
    configurer(monkeypatch, tmp_path, None)
    with Base(racine / "data" / "freinet.db"):
        pass
    assert heartbeat.main(["--racine", str(racine), "--sans-page"]) == 1
    assert notifications == ["aucun élève (python -m freinet.eleves ajouter …)"]
