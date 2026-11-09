"""La partie générale du jour, commune à tous les élèves : fonction de la seule date (inv. 6).

Mot : rang du jour depuis `origine` → langue de la rotation → mot suivant de cette langue.
Énigme : type du jour de la semaine → énigme suivante de ce type. Ce jour-là : le fait du
MM-JJ. Deux élèves de même langue, même date → même bloc ; la rotation est celle des
listes (`Listes.rotation`, PROF-12). La météo (`meteo.py`) et le profil de l'élève s'y
ajoutent dans `Partie`, que le plan du jour fige (`plan.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from freinet.general import ConfigGeneral, Enigme, Fait, Listes, Mot
from freinet.langue import LANGUE_PAR_DEFAUT
from freinet.meteo import Meteo

TYPE_PAR_JOUR = ("logique", "mots", "chiffres", "logique", "mots", "chiffres", "logique")


@dataclass(frozen=True)
class BlocGeneral:
    mot: Mot
    fait: Fait
    enigme: Enigme


@dataclass(frozen=True)
class Partie:
    """Ce que le plan d'un élève reçoit en plus de sa sélection."""

    prenom: str
    mot_de: str | None
    ville: str
    meteo: Meteo | None
    bloc: BlocGeneral
    langue: str = LANGUE_PAR_DEFAUT


def _rang_du_type(jour: date, origine: date, type_enigme: str) -> int:
    """Combien de jours de ce type entre `origine` et `jour` (négatif avant l'origine)."""
    semaines, reste = divmod((jour - origine).days, 7)
    avant = sum(
        1 for i in range(reste) if TYPE_PAR_JOUR[(origine.weekday() + i) % 7] == type_enigme
    )
    return semaines * TYPE_PAR_JOUR.count(type_enigme) + avant


def bloc_du_jour(jour: date, config: ConfigGeneral, listes: Listes) -> BlocGeneral:
    ecart = (jour - config.origine).days
    langue = listes.rotation[ecart % len(listes.rotation)]
    mots = [m for m in listes.mots if m.langue == langue]
    mot = mots[(ecart // len(listes.rotation)) % len(mots)]
    type_enigme = TYPE_PAR_JOUR[jour.weekday()]
    enigmes = [e for e in listes.enigmes if e.type == type_enigme]
    enigme = enigmes[_rang_du_type(jour, config.origine, type_enigme) % len(enigmes)]
    return BlocGeneral(mot, listes.faits[f"{jour:%m-%d}"], enigme)


def partie_du_jour(
    nom: str, jour: date, config: ConfigGeneral, listes: Listes, meteo: Meteo | None
) -> Partie:
    profil = config.profil(nom)
    bloc = bloc_du_jour(jour, config, listes)
    return Partie(profil.prenom, profil.mot_de, config.ville, meteo, bloc, profil.langue)
