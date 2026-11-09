"""`fanout/00_import`, partie script : ce qui se lit sans LLM dans un document de projet.

Le script relève l'origine, le projet, les parties et les URLs citées, et prépare `source.md` ;
l'étape LLM complète ensuite les concepts candidats, les anecdotes et l'ancrage projet (B28).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "fanout" / "00_import" / "output" / "source.md"

_TITRE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
# Une URL s'arrête à un espace, un chevron, un crochet ou un guillemet ; les parenthèses
# équilibrées lui appartiennent (https://fr.wikipedia.org/wiki/Foo_(bar)).
_URL = re.compile(r"https?://(?:[^\s()<>\[\]\"']|\([^\s()<>\[\]\"']*\))+")


def projet_de(document: Path) -> str:
    """Le dossier projet : celui qui contient `making_off/`, sinon le dossier du document."""
    parties = document.resolve().parts
    if "making_off" in parties:
        return parties[parties.index("making_off") - 1]
    return document.resolve().parent.name


def origine_de(document: Path) -> str:
    """Chemin du document, relatif au dossier personnel (`~/…`, à développer avec
    `Path.expanduser` par qui voudrait l'ouvrir) ; absolu s'il est ailleurs."""
    chemin = document.resolve()
    try:
        return "~/" + chemin.relative_to(Path.home()).as_posix()
    except ValueError:
        return chemin.as_posix()


def source_md(document: Path) -> str:
    texte = document.read_text(encoding="utf-8")
    parties = []
    prose = []
    dans_code = False
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith(("```", "~~~")):
            dans_code = not dans_code
            continue
        if dans_code:
            continue
        prose.append(ligne)
        trouve = _TITRE.match(ligne)
        if trouve:
            parties.append("  " * (len(trouve[1]) - 1) + f"- {trouve[2]}")
    urls = sorted({u.rstrip(".,;:!?") for u in _URL.findall("\n".join(prose))})
    lignes = [
        "---",
        "type: source",
        f"origine: {json.dumps(origine_de(document), ensure_ascii=False)}",
        f"projet: {json.dumps(projet_de(document), ensure_ascii=False)}",
        "---",
        "",
        "## Parties du document",
        "",
        *(parties or ["(aucun titre)"]),
        "",
        "## URLs citées",
        "",
        *([f"- {u}" for u in urls] or ["(aucune URL)"]),
        "",
        "## Pour l'étape LLM (00_import)",
        "",
        "- Concepts candidats : id kebab-case + une ligne (une partie = un ou plusieurs concepts).",
        "- Sources déjà citées : ouvrages « Auteur, Titre (année) » et URLs ci-dessus.",
        "- Anecdotes déjà présentes, avec leur source.",
        "- Ancrage projet : la matière des futures questions de transfert.",
    ]
    return "\n".join(lignes) + "\n"


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("document", type=Path)
    lecteur.add_argument("--sortie", type=Path, default=SORTIE)
    lecteur.add_argument("--force", action="store_true", help="écraser un source.md existant")
    options = lecteur.parse_args(arguments)
    if options.sortie.exists() and not options.force:
        print(f"{options.sortie} existe déjà (déjà complété ?) : --force pour l'écraser")
        return 1
    options.sortie.parent.mkdir(parents=True, exist_ok=True)
    options.sortie.write_text(source_md(options.document), encoding="utf-8")
    print(options.sortie)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
