import plistlib
import shutil
from pathlib import Path

import pytest

from freinet import launchd


def test_agents(tmp_path: Path) -> None:
    agents = launchd.agents(tmp_path, tmp_path / ".venv" / "bin" / "python")
    assert set(agents) == {
        "com.freinet.matin",
        "com.freinet.heartbeat",
        "com.freinet.serveur",
    }
    matin = agents["com.freinet.matin"]
    python = str(tmp_path / ".venv/bin/python")
    assert matin["ProgramArguments"] == [launchd.CAFFEINATE, "-i", python, "-m", "freinet.matin"]
    assert agents["com.freinet.heartbeat"]["ProgramArguments"] == [
        launchd.CAFFEINATE, "-i", python, "-m", "freinet.heartbeat",
    ]  # fmt: skip
    serveur = agents["com.freinet.serveur"]
    assert serveur["ProgramArguments"] == [python, "-m", "freinet.serveur"]
    assert serveur["KeepAlive"] == {"SuccessfulExit": False} and serveur["ThrottleInterval"] == 60
    assert all(a["WorkingDirectory"] == str(tmp_path) for a in agents.values())
    assert matin["StartCalendarInterval"] == {"Hour": 5, "Minute": 57}  # réveil pmset à 5 h 55
    assert agents["com.freinet.heartbeat"]["StartCalendarInterval"] == {"Hour": 7, "Minute": 0}
    environnement = matin["EnvironmentVariables"]
    assert isinstance(environnement, dict) and "/opt/homebrew/bin" in environnement["PATH"]
    for contenu in agents.values():
        assert plistlib.loads(plistlib.dumps(contenu)) == contenu  # plist valide


def test_installer_puis_desinstaller(tmp_path: Path) -> None:
    commandes: list[list[str]] = []

    def launchctl(arguments: list[str]) -> int:
        commandes.append(arguments)
        return 0

    dossier = tmp_path / "LaunchAgents"
    ecrits = launchd.installer(tmp_path, tmp_path / "python", dossier, launchctl)
    assert sorted(p.name for p in ecrits) == [
        "com.freinet.heartbeat.plist",
        "com.freinet.matin.plist",
        "com.freinet.serveur.plist",
    ]
    assert (tmp_path / "data" / "journal").is_dir()
    assert [c[0] for c in commandes] == ["bootout", "bootstrap"] * 3
    retires = launchd.desinstaller(dossier, launchctl)
    assert len(retires) == 3 and not list(dossier.iterdir())


def test_chargement_reessaye(tmp_path: Path) -> None:
    reponses = iter([0, 5, 5, 0, 0, 0, 0, 0])  # bootout, 2 échecs de bootstrap, puis succès
    ecrits = launchd.installer(
        tmp_path, tmp_path / "python", tmp_path / "LA", lambda _: next(reponses), 0
    )
    assert len(ecrits) == 3


def test_installation_refusee(tmp_path: Path) -> None:
    try:
        launchd.installer(tmp_path, tmp_path / "python", tmp_path / "LA", lambda _: 1, 0)
    except OSError as erreur:
        assert "n'a pas chargé" in str(erreur)
    else:
        raise AssertionError("un échec de launchctl doit être signalé")


def test_afficher(capsys: pytest.CaptureFixture[str]) -> None:
    assert launchd.main(["afficher"]) == 0
    sortie = capsys.readouterr().out
    assert "com.freinet.matin.plist" in sortie and launchd.PMSET in sortie


def test_avertissements(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda *_, **__: None)
    bureau = Path.home() / "Desktop" / "FREINET"
    messages = launchd.avertissements(bureau)
    assert any("~/Desktop" in m for m in messages) and any("claude" in m for m in messages)
    monkeypatch.setattr(shutil, "which", lambda *_, **__: "/opt/homebrew/bin/claude")
    assert launchd.avertissements(tmp_path) == []
