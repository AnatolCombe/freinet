"""Ce que la police du ticket sait dessiner (`polices/couverture.txt`).

Un glyphe absent s'imprimerait vide : « rendement ≥ 5 % » deviendrait « rendement  5 % ». Le
fan-out refuse donc un texte qui sort de la couverture, et le rendu remplace un caractère absent
par « ? » (visible) plutôt que de l'effacer. `visuel` met l'hébreu dans l'ordre d'affichage.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from pathlib import Path

COUVERTURE = Path(__file__).resolve().parent / "polices" / "couverture.txt"
REMPLACEMENT = "?"


@cache
def _points() -> frozenset[int]:
    points: set[int] = set()
    for ligne in COUVERTURE.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        debut, _, fin = ligne.partition("-")
        points.update(range(int(debut, 16), int(fin or debut, 16) + 1))
    return frozenset(points)


def absents(texte: str) -> str:
    """Les caractères (après composition NFC) que la police ne sait pas dessiner, triés."""
    connus = _points()
    texte = unicodedata.normalize("NFC", texte)
    return "".join(sorted({c for c in texte if ord(c) not in connus and not c.isspace()}))


def imprimable(texte: str) -> str:
    connus = _points()
    return "".join(
        c if ord(c) in connus or c.isspace() else REMPLACEMENT
        for c in unicodedata.normalize("NFC", texte)
    )


_HEBREU = re.compile(r"[\u0590-\u05ff]+(?: [\u0590-\u05ff]+)*")


def visuel(ligne: str) -> str:
    """L'ordre d'affichage d'une ligne pour un moteur sans bidi (Pillow en BASIC) : chaque
    suite de mots hébreux est retournée, le reste garde l'ordre logique. Juste pour un mot ou
    une courte expression dans une phrase française, sans niqqud (les listes le refusent)."""
    return _HEBREU.sub(lambda trouve: trouve.group(0)[::-1], ligne)
