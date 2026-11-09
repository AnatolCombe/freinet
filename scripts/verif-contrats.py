#!/usr/bin/env python3
"""Inv. 12 : tout dossier d'étape (`fanout/NN_*`, `quotidien/NN_*`) a un `CONTEXT.md` au contrat
ICM — Inputs (une ligne Working, une ligne Reference), Process, Outputs, et une seule
vérification humaine (une seule ligne sous « Human check »). Code 0 si tout est conforme."""

from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PIPELINES = ("fanout", "quotidien")
_ETAPE = re.compile(r"^\d\d_")
SECTIONS = ("Inputs", "Process", "Outputs", "Human check")


def _sections(texte: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    courante = None
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            courante = ligne[3:].split(" (")[0].strip()
            sections[courante] = []
        elif courante is not None and ligne.strip():
            sections[courante].append(ligne.strip())
    return sections


def defauts(racine: Path = RACINE) -> list[str]:
    problemes = []
    for pipeline in PIPELINES:
        for etape in sorted(p for p in (racine / pipeline).iterdir() if _ETAPE.match(p.name)):
            nom = f"{pipeline}/{etape.name}"
            contrat = etape / "CONTEXT.md"
            if not contrat.is_file():
                problemes.append(f"{nom} : CONTEXT.md absent")
                continue
            sections = _sections(contrat.read_text(encoding="utf-8"))
            for titre in SECTIONS:
                if not sections.get(titre):
                    problemes.append(f"{nom} : section « {titre} » absente ou vide")
            entrees = sections.get("Inputs", [])
            for genre in ("Working", "Reference"):
                if not any(e.lstrip("- ").startswith(genre) for e in entrees):
                    problemes.append(f"{nom} : Inputs sans ligne « {genre} »")
            if len(sections.get("Human check", [])) > 1:
                problemes.append(f"{nom} : plus d'une vérification humaine")
    return problemes


def main() -> int:
    problemes = defauts()
    for probleme in problemes:
        print(probleme, file=sys.stderr)
    return 1 if problemes else 0


if __name__ == "__main__":
    raise SystemExit(main())
