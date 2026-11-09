#!/usr/bin/env python3
"""Régénère `bibliotheque/index.md` ; `--check` échoue si le fichier diffère (inv. 13)."""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from freinet.bibliotheque import charger  # noqa: E402
from freinet.frontmatter import ErreurContenu  # noqa: E402
from freinet.index import generer_index  # noqa: E402


def main(arguments: list[str], racine: Path = RACINE) -> int:
    index = racine / "bibliotheque" / "index.md"
    try:
        attendu = generer_index(charger(racine / "bibliotheque"))
    except ErreurContenu as erreur:
        print(f"bibliothèque invalide, index non généré : {erreur}", file=sys.stderr)
        return 1
    if "--check" in arguments:
        if not index.is_file() or index.read_text(encoding="utf-8") != attendu:
            print(f"{index} n'est pas à jour : lancer scripts/regen-index.py", file=sys.stderr)
            return 1
        return 0
    index.write_text(attendu, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
