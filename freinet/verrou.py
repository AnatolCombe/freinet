"""Un seul rituel à la fois (#53) : le matin, l'impression à la main et le heartbeat prennent
le même verrou (`data/matin.lock`, `flock`). Deux lancements simultanés (agent launchd et
commande à la main, ou réveil tardif) ne peuvent donc ni doubler un ticket, ni faire croire
au heartbeat qu'un ticket manque pendant qu'il s'imprime.
"""

from __future__ import annotations

import fcntl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ATTENTE_S = 600.0  # le matin peut attendre le LLM (60 s) et l'impression (90 s) de chaque élève


class VerrouOccupe(TimeoutError):
    """Un autre rituel tient le verrou depuis trop longtemps."""


@contextmanager
def verrou_du_rituel(racine: Path, attente: float = ATTENTE_S) -> Iterator[None]:
    chemin = racine / "data" / "matin.lock"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a") as fichier:
        limite = time.monotonic() + attente
        while True:
            try:
                fcntl.flock(fichier, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= limite:
                    raise VerrouOccupe(f"un autre rituel est en cours ({chemin})") from None
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(fichier, fcntl.LOCK_UN)
