"""La couche LLM du matin (#19) : une phrase du coach par `claude -p`, avec repli (inv. 7).

Le LLM ne lit jamais la base (inv. 2) : il reçoit un résumé texte du jour (`contexte`), tiré
de la sélection. Sa réponse est contrôlée comme tout ce qui s'imprime : une ligne, courte,
sans lien ni balisage (#45), dessinable par la police du ticket. Au moindre écart (commande
absente, délai, erreur, réponse hors règles), la phrase par défaut sort : le ticket ne dépend
jamais du LLM. `FREINET_SANS_LLM=1` le coupe ; `FREINET_CLAUDE` donne le chemin de la
commande (launchd a un PATH appauvri). La commande tourne dans un dossier vide, sans outils
ni serveurs MCP : elle ne voit que le résumé (inv. 2). La consigne vient de `langue.py`, dans
la langue de l'élève (PROF-12).
"""

from __future__ import annotations

import contextlib
import json
import os
import select
import shutil
import signal
import subprocess
import tempfile
import time

from freinet.imprimable import absents
from freinet.langue import FR
from freinet.selection import Selection
from freinet.validation import contient_lien

SANS_LLM = "FREINET_SANS_LLM"
COMMANDE = "FREINET_CLAUDE"
DELAI_S = 60.0
LONGUEUR_MAX = 90
SORTIE_MAX = 65536  # une réponse plus longue n'est pas une phrase : refusée sans la lire


def llm_coupe() -> bool:
    return os.environ.get(SANS_LLM, "").strip().lower() in {"1", "oui", "true", "yes"}


def contexte(selection: Selection) -> str:
    """Le résumé texte du jour que reçoit le LLM (jamais la base, inv. 2)."""
    lignes = [f"Jour : {selection.jour.isoformat()}"]
    if selection.reprise:
        lignes.append("Reprise après une pause : rien à rattraper, on repart doucement.")
    if selection.nouvelle:
        lignes.append(f"Notion nouvelle : {selection.nouvelle.titre}")
    lignes.append(f"Révisions : {len(selection.revisions)}")
    if selection.quete:
        q = selection.quete
        lignes.append(f"Quête : {q.objectif} ({q.acquis}/{q.total})")
    return "\n".join(lignes)


def phrase_valide(texte: str) -> str | None:
    """La phrase si elle respecte les règles de ce qui s'imprime, sinon `None`."""
    phrase = " ".join(texte.split()).strip("\"'« »")
    if not phrase or len(phrase) > LONGUEUR_MAX or "\n" in texte.strip():
        return None
    if contient_lien(phrase) or absents(phrase):
        return None
    return phrase


def _lire_borne(processus: subprocess.Popen[bytes], echeance: float) -> bytes | None:
    """La sortie, lue par morceaux jusqu'à la fin, l'échéance ou `SORTIE_MAX` (rien au-delà)."""
    assert processus.stdout is not None
    lu = bytearray()
    while len(lu) <= SORTIE_MAX:
        reste = echeance - time.monotonic()
        if reste <= 0 or not select.select([processus.stdout], [], [], reste)[0]:
            return None
        morceau = os.read(processus.stdout.fileno(), 65536)
        if not morceau:
            return bytes(lu)
        lu += morceau
    return None


def _appeler(appel: list[str], resume: str, delai: float) -> str | None:
    """Lance la commande dans un dossier vide (ni CLAUDE.md, ni réglages du projet, ni accès aux
    données), le résumé sur l'entrée standard. Délai et taille bornés : au moindre dépassement,
    tout son groupe de processus est tué et l'on n'attend plus rien de lui."""
    with tempfile.TemporaryDirectory() as vide:
        processus = subprocess.Popen(
            appel,
            cwd=vide,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        echeance = time.monotonic() + delai
        try:
            assert processus.stdin is not None
            with contextlib.suppress(BrokenPipeError):
                processus.stdin.write(resume.encode("utf-8"))
            with contextlib.suppress(BrokenPipeError):
                processus.stdin.close()
            sortie = _lire_borne(processus, echeance)
            if sortie is not None:
                processus.wait(timeout=max(0.1, echeance - time.monotonic()))
        except subprocess.TimeoutExpired:
            sortie = None
        finally:
            if processus.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(processus.pid, signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    processus.wait(timeout=5)
            if processus.stdout is not None:
                processus.stdout.close()
    if sortie is None or processus.returncode != 0:
        return None
    return sortie.decode("utf-8", "replace")


def phrase_du_coach(
    resume: str, defaut: str, delai: float = DELAI_S, systeme: str = FR.coach_systeme
) -> str:
    """La phrase du LLM, ou `defaut` au moindre écart (inv. 7). `systeme` : la consigne, dans
    la langue de l'élève (`langue.py`) ; le résumé reste en français, le LLM répond dans la
    langue de la consigne."""
    if llm_coupe():
        return defaut
    commande = os.environ.get(COMMANDE) or shutil.which("claude")
    if not commande:
        return defaut
    appel = [
        commande, "-p", "--output-format", "json", "--model", "haiku",
        "--system-prompt", systeme, "--tools", "", "--strict-mcp-config",
        "--no-session-persistence",
    ]  # fmt: skip
    try:
        sortie = _appeler(appel, resume, delai)
        resultat = json.loads(sortie)["result"] if sortie is not None else None
    except (OSError, ValueError, KeyError, TypeError):
        return defaut
    return (phrase_valide(resultat) if isinstance(resultat, str) else None) or defaut
