"""Dose et dosage, lus dans `_config/dose.md` (inv. 14 : le coach bouge dans les bornes)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from freinet.frontmatter import ErreurContenu

FICHIER_DOSE = Path(__file__).resolve().parent.parent / "_config" / "dose.md"


@dataclass(frozen=True)
class Dose:
    revisions: int
    revisions_min: int
    revisions_max: int
    nouvelles: int
    nouvelles_max: int
    week_end: tuple[int, int, int]  # projets / déclarés / sérendipité (A2)
    reprise_jours: int

    def borner_revisions(self, demande: int) -> int:
        """Ce qu'un réglage (coach, élève) peut demander, ramené dans les bornes fixes."""
        return max(self.revisions_min, min(self.revisions_max, demande))


_REPRISE = re.compile(r"Apr[eè]s\s*(?:≥|>=)\s*(\d+)\s*jours", re.IGNORECASE)


def _nombres(cellule: str) -> list[int]:
    """Les entiers d'une cellule, notes entre parenthèses ignorées (« 0 / 0 / 100 (A2) ») ;
    un « - » collé à un chiffre est un séparateur (« 1-5 »), pas un signe."""
    return [int(n) for n in re.findall(r"(?<!\d)-?\d+", re.sub(r"\([^)]*\)", "", cellule))]


def _cellules(texte: str, libelle: str, chemin: Path) -> list[str]:
    trouvees = []
    for ligne in texte.splitlines():
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if cellules[0].strip("* ").casefold().startswith(libelle):
            trouvees.append(cellules)
    if not trouvees:
        raise ErreurContenu(chemin, f"ligne « {libelle} » absente")
    if len(trouvees) > 1:
        raise ErreurContenu(chemin, f"ligne « {libelle} » en double")
    if len(trouvees[0]) < 3:
        raise ErreurContenu(chemin, f"ligne « {libelle} » : colonnes Défaut et Bornes attendues")
    return trouvees[0]


def _defaut_et_bornes(texte: str, libelle: str, chemin: Path) -> tuple[int, int, int]:
    cellules = _cellules(texte, libelle, chemin)
    defaut, bornes = _nombres(cellules[1]), _nombres(cellules[2])
    if len(defaut) != 1 or len(bornes) != 2 or bornes[0] < 0:
        raise ErreurContenu(chemin, f"ligne « {libelle} » : un défaut et deux bornes positives")
    return defaut[0], bornes[0], bornes[1]


def lire_dose(chemin: Path = FICHIER_DOSE) -> Dose:
    texte = chemin.read_text(encoding="utf-8")
    revisions, revisions_min, revisions_max = _defaut_et_bornes(
        texte, "révisions par ticket", chemin
    )
    nouvelles, _nouvelles_min, nouvelles_max = _defaut_et_bornes(
        texte, "notions nouvelles par ticket", chemin
    )
    week_end = _nombres(_cellules(texte, "dosage week-end", chemin)[1])
    if len(week_end) != 3 or sum(week_end) != 100 or min(week_end) < 0:
        raise ErreurContenu(chemin, "ligne « dosage week-end » : trois parts qui font 100")
    reprise = _REPRISE.search(texte)
    if reprise is None:
        raise ErreurContenu(chemin, "seuil de reprise « Après ≥ N jours » absent")
    dose = Dose(
        revisions=revisions,
        revisions_min=revisions_min,
        revisions_max=revisions_max,
        nouvelles=nouvelles,
        nouvelles_max=nouvelles_max,
        week_end=(week_end[0], week_end[1], week_end[2]),
        reprise_jours=int(reprise[1]),
    )
    if not dose.revisions_min <= dose.revisions <= dose.revisions_max:
        raise ErreurContenu(chemin, "révisions par défaut hors de leurs bornes")
    if not 0 <= dose.nouvelles <= dose.nouvelles_max <= 1:
        raise ErreurContenu(chemin, "notions nouvelles : au plus 1 par ticket (inv. 14)")
    return dose
