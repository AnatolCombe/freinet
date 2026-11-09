import json
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from freinet.coach import LONGUEUR_MAX, contexte, phrase_du_coach, phrase_valide
from freinet.langue import EN
from tests.selection.scenario import reponse, selection


def _faux_claude(tmp_path: Path, sortie: str, code: int = 0, attente: float = 0) -> Path:
    """Une commande `claude` factice : elle garde ses arguments et répond `sortie`."""
    script = tmp_path / "claude"
    script.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$@" > "{tmp_path}/arguments"\n'
        f'pwd > "{tmp_path}/dossier"\n'
        f'cat > "{tmp_path}/entree"\n'
        f"sleep {attente}\n"
        f"cat <<'FIN'\n{sortie}\nFIN\n"
        f"exit {code}\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


@pytest.fixture
def avec_llm(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.delenv("FREINET_SANS_LLM")
    return monkeypatch


def _resultat(texte: str) -> str:
    return json.dumps({"type": "result", "result": texte})


def test_la_phrase_du_llm(tmp_path: Path, avec_llm: pytest.MonkeyPatch) -> None:
    commande = _faux_claude(tmp_path, _resultat("« Une tierce à la fois, sans te presser. »"))
    avec_llm.setenv("FREINET_CLAUDE", str(commande))
    assert (
        phrase_du_coach("Jour : 2026-01-05", "défaut") == "Une tierce à la fois, sans te presser."
    )
    arguments = (tmp_path / "arguments").read_text(encoding="utf-8").splitlines()
    assert arguments[0] == "-p" and "haiku" in arguments
    assert arguments[arguments.index("--tools") + 1] == ""  # aucun outil (inv. 2)
    assert {"--strict-mcp-config", "--no-session-persistence"} <= set(arguments)
    assert (tmp_path / "entree").read_text(encoding="utf-8") == "Jour : 2026-01-05"  # stdin
    dossier = Path((tmp_path / "dossier").read_text(encoding="utf-8").strip()).resolve()
    racine = Path(__file__).resolve().parents[2]
    assert not dossier.is_relative_to(racine) and not dossier.exists()  # dossier vide, jetable


@pytest.mark.parametrize(
    ("sortie", "code"),
    [
        (_resultat("x" * (LONGUEUR_MAX + 1)), 0),  # trop longue
        (_resultat("Va voir https://exemple.fr"), 0),  # lien (#45)
        (_resultat("Deux lignes\nau lieu d'une"), 0),
        (_resultat("Courage 🎵"), 0),  # hors police du ticket
        (_resultat(""), 0),
        ("pas du json", 0),
        (json.dumps({"autre": 1}), 0),
        (json.dumps(["liste"]), 0),
        (_resultat("Bien."), 1),  # la commande échoue
    ],
)
def test_repli_au_moindre_ecart(
    tmp_path: Path, avec_llm: pytest.MonkeyPatch, sortie: str, code: int
) -> None:
    avec_llm.setenv("FREINET_CLAUDE", str(_faux_claude(tmp_path, sortie, code)))
    assert phrase_du_coach("Jour", "défaut") == "défaut"


def test_repli_si_le_llm_traine(tmp_path: Path, avec_llm: pytest.MonkeyPatch) -> None:
    avec_llm.setenv("FREINET_CLAUDE", str(_faux_claude(tmp_path, _resultat("Bien."), 0, 5)))
    assert phrase_du_coach("Jour", "défaut", delai=0.5) == "défaut"


def test_delai_tue_tout_le_groupe(tmp_path: Path, avec_llm: pytest.MonkeyPatch) -> None:
    """Un `claude` qui lance un sous-processus (node, MCP) : au délai, rien ne survit."""
    trace = tmp_path / "petit-fils"
    script = tmp_path / "claude"
    script.write_text(f"#!/bin/sh\n(sleep 30; touch {trace}) &\nsleep 30\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    avec_llm.setenv("FREINET_CLAUDE", str(script))
    assert phrase_du_coach("Jour", "défaut", delai=0.5) == "défaut"
    time.sleep(1)
    tues = subprocess.run(["pgrep", "-f", f"touch {trace}"], capture_output=True)
    assert tues.returncode == 1  # plus aucun processus du groupe


def test_reponse_demesuree(tmp_path: Path, avec_llm: pytest.MonkeyPatch) -> None:
    avec_llm.setenv("FREINET_CLAUDE", str(_faux_claude(tmp_path, "x" * 70000)))
    assert phrase_du_coach("Jour", "défaut") == "défaut"


@pytest.mark.parametrize("valeur", ["0", "", "non"])
def test_sans_llm_seulement_si_demande(
    tmp_path: Path, avec_llm: pytest.MonkeyPatch, valeur: str
) -> None:
    avec_llm.setenv("FREINET_SANS_LLM", valeur)
    avec_llm.setenv("FREINET_CLAUDE", str(_faux_claude(tmp_path, _resultat("Allez."))))
    assert phrase_du_coach("Jour", "défaut") == "Allez."


def test_repli_sans_commande(avec_llm: pytest.MonkeyPatch) -> None:
    avec_llm.delenv("FREINET_CLAUDE", raising=False)
    avec_llm.setattr(shutil, "which", lambda _: None)
    assert phrase_du_coach("Jour", "défaut") == "défaut"
    avec_llm.setenv("FREINET_CLAUDE", "/nulle/part/claude")
    assert phrase_du_coach("Jour", "défaut") == "défaut"


def test_ticket_sans_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Inv. 7 : LLM coupé par la variable d'environnement, la commande n'est jamais lancée."""
    monkeypatch.setenv("FREINET_SANS_LLM", "1")
    monkeypatch.setenv("FREINET_CLAUDE", str(_faux_claude(tmp_path, _resultat("LLM !"))))
    assert phrase_du_coach("Jour", "défaut") == "défaut"
    assert not (tmp_path / "arguments").exists()


def test_contexte_sans_la_base() -> None:
    s = selection([reponse(1, "intervalle-q1", 4, 0), reponse(2, "intervalle-q2", 1, 1)], 5)
    texte = contexte(s)
    assert "Reprise après une pause" in texte and "Révisions : 1" in texte
    assert "Quête : Reconnaître une cadence parfaite à l'oreille (0/4)" in texte
    assert "Notion nouvelle : Intervalle" in contexte(selection([]))


def test_phrase_valide() -> None:
    assert phrase_valide("  Un pas,  puis un autre.  ") == "Un pas, puis un autre."
    assert phrase_valide('"Guillemets retirés."') == "Guillemets retirés."


def test_delai_tenu_meme_si_un_descendant_s_echappe(
    tmp_path: Path, avec_llm: pytest.MonkeyPatch
) -> None:
    """Un descendant qui quitte le groupe (setsid) en gardant la sortie ouverte : on ne
    l'attend pas, le délai tient."""
    script = tmp_path / "claude"
    evasion = "import os, time\nif os.fork() == 0:\n    os.setsid()\ntime.sleep(3)\n"
    script.write_text(f"#!{sys.executable}\n{evasion}", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    avec_llm.setenv("FREINET_CLAUDE", str(script))
    debut = time.monotonic()
    assert phrase_du_coach("Jour", "défaut", delai=0.5) == "défaut"
    assert time.monotonic() - debut < 8


def test_consigne_dans_la_langue(tmp_path: Path, avec_llm: pytest.MonkeyPatch) -> None:
    commande = _faux_claude(tmp_path, _resultat("One trade at a time."))
    avec_llm.setenv("FREINET_CLAUDE", str(commande))
    assert phrase_du_coach("Jour : 2026-01-05", "x", systeme=EN.coach_systeme) == (
        "One trade at a time."
    )
    arguments = (tmp_path / "arguments").read_text(encoding="utf-8").splitlines()
    assert "in English" in arguments[arguments.index("--system-prompt") + 1]
