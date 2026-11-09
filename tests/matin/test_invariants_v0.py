"""Invariants 2, 11 et 12 du PRD §4, et la vérification V0 (§5)."""

import ast
import importlib.util
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

RACINE = Path(__file__).resolve().parents[2]
ETAPES_LLM = [
    *(RACINE / "fanout").glob("0[1-5]_*"),  # rédaction par agents (cadrage → vérification)
    RACINE / "quotidien" / "02_plan",  # phrase du coach (#19)
]
MODULES_LLM = [RACINE / "freinet" / "coach.py"]


def _script(nom: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        nom.replace("-", "_"), RACINE / "scripts" / f"{nom}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entrees(contrat: Path) -> str:
    texte = contrat.read_text(encoding="utf-8")
    return texte.split("## Inputs", 1)[1].split("\n## ", 1)[0]


def test_contrats_llm() -> None:
    """Inv. 2 : une étape LLM ne reçoit que des exports texte, jamais la base."""
    assert len(ETAPES_LLM) == 6
    for etape in ETAPES_LLM:
        entrees = _entrees(etape / "CONTEXT.md")
        assert ".db" not in entrees and "data/" not in entrees, etape.name
    for module in MODULES_LLM:
        arbre = ast.parse(module.read_text(encoding="utf-8"))
        importes = {
            n.module for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) and n.module
        } | {a.name for n in ast.walk(arbre) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m == "sqlite3" or m.startswith("freinet.base") for m in importes)


def test_un_seul_appel_au_llm() -> None:
    """Toute nouvelle commande `claude` dans le code doit passer par `coach.py` (inv. 2)."""
    appels = [
        f.relative_to(RACINE).as_posix()
        for f in (RACINE / "freinet").rglob("*.py")
        if '"claude"' in f.read_text(encoding="utf-8")
    ]
    # launchd.py ne fait que localiser la commande (FREINET_CLAUDE), sans jamais la lancer.
    assert sorted(appels) == ["freinet/coach.py", "freinet/launchd.py"]
    lanceurs = [a for a in appels if "subprocess" in (RACINE / a).read_text(encoding="utf-8")]
    assert "freinet/coach.py" in lanceurs
    assert '"-p"' not in (RACINE / "freinet/launchd.py").read_text(encoding="utf-8")


def test_llm_en_panne_le_ticket_sort_quand_meme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inv. 7 de bout en bout : la commande échoue, le plan porte la phrase par défaut."""
    from freinet import quotidien
    from freinet.frontmatter import lire
    from freinet.langue import FR
    from tests.matin.scenario import LUNDI_6H, racine_matin

    panne = tmp_path / "claude"
    panne.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    panne.chmod(0o755)
    monkeypatch.delenv("FREINET_SANS_LLM")
    monkeypatch.setenv("FREINET_CLAUDE", str(panne))
    racine = racine_matin(tmp_path / "r", ("marius",))
    arguments = ["--racine", str(racine), "--eleve", "marius", "--instant", LUNDI_6H]
    assert quotidien.main(arguments) == 0
    _, corps = lire(racine / "brainiacs" / "marius" / "plans" / "2026-01-05.md")
    assert f"> {FR.phrase_defaut}" in corps


@pytest.mark.skipif(shutil.which("git") is None, reason="git absent")
def test_confidentialite_profil(tmp_path: Path) -> None:
    """Inv. 11 et #21 : profil, base, plans, tickets et clé d'accès ne sont jamais versionnés."""
    depot = tmp_path / "depot"
    depot.mkdir()
    subprocess.run(["git", "init", "-q", str(depot)], check=True)
    shutil.copy(RACINE / ".gitignore", depot / ".gitignore")
    prives = [
        "brainiacs/marius/profil/faits.md",
        "brainiacs/marius/plans/2026-01-05.md",
        "data/freinet.db",
        "data/.cle-acces",
        "data/journal/matin.log",
        "quotidien/03_rendu/output/marius/acces-2026-01-05.txt",
        "quotidien/03_rendu/output/marius/ticket-2026-01-05.png",
    ]
    ignores = subprocess.run(
        ["git", "-C", str(depot), "check-ignore", *prives], capture_output=True, text=True
    ).stdout.split()
    assert ignores == prives
    publics = ["brainiacs/_index/catalogue.md", "bibliotheque/index.md"]
    assert subprocess.run(["git", "-C", str(depot), "check-ignore", *publics]).returncode == 1
    for fichier in (RACINE / "bibliotheque").rglob("*.md"):
        assert "access_tier: prive" not in fichier.read_text(encoding="utf-8"), fichier


def test_contrats_icm() -> None:
    """Inv. 12 : `scripts/verif-contrats.py` → aucun défaut."""
    assert _script("verif-contrats").defauts() == []


def test_contrat_non_conforme_signale(tmp_path: Path) -> None:
    etape = tmp_path / "quotidien" / "09_essai"
    etape.mkdir(parents=True)
    (tmp_path / "fanout").mkdir()
    (etape / "CONTEXT.md").write_text(
        "## Inputs\n- Working : x\n## Process\n1. y\n## Human check\nun\ndeux\n", "utf-8"
    )
    (tmp_path / "quotidien" / "10_vide").mkdir()
    assert _script("verif-contrats").defauts(tmp_path) == [
        "quotidien/09_essai : section « Outputs » absente ou vide",
        "quotidien/09_essai : Inputs sans ligne « Reference »",
        "quotidien/09_essai : plus d'une vérification humaine",
        "quotidien/10_vide : CONTEXT.md absent",
    ]


def test_verif_v0(capsys: pytest.CaptureFixture[str]) -> None:
    """PRD §5, étapes 1 à 5 (la 6e, la suite elle-même, est dans `verif-v0.sh`)."""
    assert _script("verif_v0").main() == 0
    assert "FSRS : raté → revient, réussi → repoussé" in capsys.readouterr().out
