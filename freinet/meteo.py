"""La météo du jour (Open-Meteo, sans clé) : un appel au passage du matin, figé dans le plan.

Réseau optionnel (inv. 7) : délai, erreur HTTP, réponse malformée → `None`, une ligne sur la
sortie d'erreur, et le ticket sort sans météo. `FREINET_SANS_RESEAU=1` coupe l'appel (tests,
vérification V0). Une fois écrit, le plan garde la météo : une réimpression ne rappelle pas le
réseau et rend le même ticket.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode
from urllib.request import urlopen

from freinet.general import ConfigGeneral
from freinet.langue import FR, Libelles

SANS_RESEAU = "FREINET_SANS_RESEAU"
API = "https://api.open-meteo.com/v1/forecast"
DELAI_S = 5.0
TAILLE_MAX = 65536  # une réponse plus longue n'est pas la météo d'un jour
DIRECTIONS = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
# Valeurs françaises : clés des libellés (`langue.py`), traduites à l'écriture du plan.
MOMENTS = (("la nuit", 0, 6), ("le matin", 6, 12), ("l'après-midi", 12, 18), ("le soir", 18, 24))
QUOTIDIEN = (
    "temperature_2m_min,temperature_2m_max,precipitation_probability_max,"
    "wind_speed_10m_max,wind_direction_10m_dominant,sunrise,sunset"
)
_HEURE = re.compile(r"\d\d:\d\d")


@dataclass(frozen=True)
class Meteo:
    minimum: int  # °C
    maximum: int
    pluie: int  # probabilité maximale du jour, en %
    moment: str | None  # quand la pluie est la plus probable, si elle atteint le seuil
    vent: int  # km/h, vent moyen maximal
    direction: str  # N, NE, … (dominante)
    lever: str  # HH:MM, heure locale
    coucher: str

    def lignes(self, lib: Libelles = FR) -> list[str]:
        moment = lib.meteo_moment.format(moment=lib.moments[self.moment]) if self.moment else ""
        return [
            lib.meteo_temperature.format(
                minimum=self.minimum,
                maximum=self.maximum,
                vent=self.vent,
                direction=lib.directions[self.direction],
            ),
            lib.meteo_pluie.format(pluie=self.pluie) + moment,
            lib.meteo_soleil.format(lever=lib.heure(self.lever), coucher=lib.heure(self.coucher)),
        ]


def url(jour: date, config: ConfigGeneral) -> str:
    parametres = {
        "latitude": config.latitude,
        "longitude": config.longitude,
        "timezone": config.fuseau,
        "start_date": jour.isoformat(),
        "end_date": jour.isoformat(),
        "daily": QUOTIDIEN,
        "hourly": "precipitation_probability",
    }
    return f"{API}?{urlencode(parametres)}"


def _moment(horaires: list[int]) -> str | None:
    """Le moment de la journée où la pluie est la plus probable (24 valeurs horaires)."""
    if len(horaires) < 24:
        return None
    return max(MOMENTS, key=lambda m: max(horaires[m[1] : m[2]]))[0]


def lire_reponse(donnees: object, seuil: int) -> Meteo:
    """La réponse d'Open-Meteo pour un jour ; `ValueError` si un champ manque ou est hors type."""
    if not isinstance(donnees, dict):
        raise ValueError("réponse météo : objet JSON attendu")
    try:
        jour = donnees["daily"]
        horaires = [int(p or 0) for p in donnees["hourly"]["precipitation_probability"]]
        pluie = int(jour["precipitation_probability_max"][0] or 0)
        meteo = Meteo(
            minimum=round(float(jour["temperature_2m_min"][0])),
            maximum=round(float(jour["temperature_2m_max"][0])),
            pluie=pluie,
            moment=_moment(horaires) if pluie >= seuil else None,
            vent=round(float(jour["wind_speed_10m_max"][0])),
            direction=DIRECTIONS[round(float(jour["wind_direction_10m_dominant"][0]) / 45) % 8],
            lever=str(jour["sunrise"][0]).rpartition("T")[2],
            coucher=str(jour["sunset"][0]).rpartition("T")[2],
        )
    except (KeyError, IndexError, TypeError) as erreur:
        raise ValueError(f"réponse météo incomplète ({erreur!r})") from None
    if not (_HEURE.fullmatch(meteo.lever) and _HEURE.fullmatch(meteo.coucher)):
        raise ValueError(f"réponse météo : heures illisibles ({meteo.lever}, {meteo.coucher})")
    return meteo


def telecharger(adresse: str) -> bytes:
    with urlopen(adresse, timeout=DELAI_S) as reponse:  # adresse fixe en https (API)
        corps: bytes = reponse.read(TAILLE_MAX + 1)
    if len(corps) > TAILLE_MAX:
        raise ValueError("réponse météo trop longue")
    return corps


def meteo_du_jour(
    jour: date, config: ConfigGeneral, telecharge: Callable[[str], bytes] = telecharger
) -> Meteo | None:
    if os.environ.get(SANS_RESEAU, "").strip().lower() in {"1", "oui", "true", "yes"}:
        return None
    try:
        return lire_reponse(json.loads(telecharge(url(jour, config))), config.seuil_pluie)
    except (
        OSError,
        ValueError,
        http.client.HTTPException,
        ArithmeticError,
        RecursionError,
    ) as erreur:
        # URLError et délai : OSError ; JSON et UTF-8 invalides : ValueError ;
        # valeurs infinies ou démesurées : ArithmeticError ; JSON trop imbriqué : RecursionError.
        print(f"météo indisponible : {str(erreur) or type(erreur).__name__}", file=sys.stderr)
        return None
