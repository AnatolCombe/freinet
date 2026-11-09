"""Constantes de la règle « acquis », lues dans `_config/regle-acquis.md` (inv. 5).

Le fichier Markdown est la seule source : aucune valeur n'est recopiée dans le code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_REGLE = RACINE / "_config" / "regle-acquis.md"

_LIGNE = re.compile(r"^\|\s*`(?P<nom>[A-Z0-9_]+)`\s*\|\s*(?P<valeur>[^\s|]+)")


@dataclass(frozen=True)
class ReglesAcquis:
    retention: float
    horizon_jours: int
    transferts_requis: int

    def __post_init__(self) -> None:
        if not 0 < self.retention <= 1:
            raise ValueError(f"RETENTION_ACQUIS hors de ]0, 1] : {self.retention}")
        if self.horizon_jours <= 0:
            raise ValueError(f"HORIZON_ACQUIS_JOURS doit être > 0 : {self.horizon_jours}")
        if self.transferts_requis < 0:
            raise ValueError(f"TRANSFERT_REQUIS doit être ≥ 0 : {self.transferts_requis}")


def lire_regles(chemin: Path = FICHIER_REGLE) -> ReglesAcquis:
    """Lit les lignes `| \\`NOM\\` | valeur — commentaire |` du tableau des constantes.

    Refuse une constante absente, en double, illisible ou hors bornes."""
    valeurs: dict[str, str] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        trouve = _LIGNE.match(ligne)
        if trouve:
            if trouve["nom"] in valeurs:
                raise ValueError(f"{chemin} : constante en double {trouve['nom']}")
            valeurs[trouve["nom"]] = trouve["valeur"]
    try:
        retention = float(valeurs["RETENTION_ACQUIS"].replace(",", "."))
        horizon_jours = int(valeurs["HORIZON_ACQUIS_JOURS"])
        transferts_requis = int(valeurs["TRANSFERT_REQUIS"])
    except KeyError as manque:
        raise ValueError(f"{chemin} : constante absente {manque}") from None
    except ValueError as erreur:
        raise ValueError(f"{chemin} : valeur illisible ({erreur})") from None
    return ReglesAcquis(retention, horizon_jours, transferts_requis)
