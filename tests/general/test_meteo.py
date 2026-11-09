import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from freinet.langue import EN
from freinet.meteo import Meteo, lire_reponse, meteo_du_jour, url
from tests.general.listes import charger, ecrire_general

JOUR = date(2026, 9, 30)
PLUIE = [0, 0, 0, 0, 0, 0, 3, 5, 3, 3, 3, 3, 3, 0, 0, 3, 3, 13, 13, 20, 23, 25, 38, 30]
REPONSE: dict[str, dict[str, list[Any]]] = {
    "hourly": {"precipitation_probability": PLUIE},
    "daily": {
        "temperature_2m_min": [18.3],
        "temperature_2m_max": [26.4],
        "precipitation_probability_max": [38],
        "wind_speed_10m_max": [29.2],
        "wind_direction_10m_dominant": [164],
        "sunrise": ["2026-09-30T07:40"],
        "sunset": ["2026-09-30T19:26"],
    },
}
ATTENDUE = Meteo(18, 26, 38, "le soir", 29, "S", "07:40", "19:26")


def test_lecture_de_la_reponse() -> None:
    meteo = lire_reponse(REPONSE, 20)
    assert meteo == ATTENDUE
    assert meteo.lignes() == [
        "18° → 26° · vent 29 km/h S",
        "Pluie 38 %, surtout le soir",
        "Soleil 7 h 40 → 19 h 26",
    ]


def test_pluie_sous_le_seuil_sans_moment() -> None:
    faible = {**REPONSE, "daily": {**REPONSE["daily"], "precipitation_probability_max": [10]}}
    meteo = lire_reponse(faible, 20)
    assert meteo.moment is None and meteo.lignes()[1] == "Pluie 10 %"


@pytest.mark.parametrize(
    "donnees",
    [
        [],
        {"daily": {}},
        {**REPONSE, "daily": {**REPONSE["daily"], "temperature_2m_min": [None]}},
        {**REPONSE, "daily": {**REPONSE["daily"], "sunrise": ["demain"]}},
    ],
)
def test_reponse_malformee(donnees: object) -> None:
    with pytest.raises(ValueError, match="météo"):
        lire_reponse(donnees, 20)


def test_url_du_jour(tmp_path: Path) -> None:
    config, _ = charger(ecrire_general(tmp_path))
    adresse = url(JOUR, config)
    assert adresse.startswith("https://api.open-meteo.com/v1/forecast?")
    assert "latitude=45.74846" in adresse and "start_date=2026-09-30" in adresse
    assert "end_date=2026-09-30" in adresse and "timezone=Europe%2FParis" in adresse


def test_repli_sans_reseau(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _ = charger(ecrire_general(tmp_path))
    appels: list[str] = []

    def telecharge(adresse: str) -> bytes:
        appels.append(adresse)
        return json.dumps(REPONSE).encode()

    assert meteo_du_jour(JOUR, config, telecharge) is None  # FREINET_SANS_RESEAU (conftest)
    assert appels == []
    monkeypatch.delenv("FREINET_SANS_RESEAU")
    assert meteo_du_jour(JOUR, config, telecharge) == ATTENDUE


@pytest.mark.parametrize("panne", [OSError("réseau coupé"), TimeoutError(), ValueError("json")])
def test_panne_donne_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    panne: Exception,
) -> None:
    monkeypatch.delenv("FREINET_SANS_RESEAU")
    config, _ = charger(ecrire_general(tmp_path))

    def telecharge(adresse: str) -> bytes:
        raise panne

    assert meteo_du_jour(JOUR, config, telecharge) is None
    assert "météo indisponible" in capsys.readouterr().err


def test_json_invalide_donne_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FREINET_SANS_RESEAU")
    config, _ = charger(ecrire_general(tmp_path))
    assert meteo_du_jour(JOUR, config, lambda adresse: b"<html>") is None


def _corps(remplacement: str) -> bytes:
    return json.dumps(REPONSE).replace("26.4", remplacement).encode()


@pytest.mark.parametrize(
    "corps",
    [_corps("Infinity"), _corps("1e999"), _corps("1" + "0" * 400), b"[" * 65536],
    ids=["infini", "exposant", "entier-demesure", "imbrique"],
)
def test_valeurs_aberrantes_donnent_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    corps: bytes,
) -> None:
    monkeypatch.delenv("FREINET_SANS_RESEAU")
    config, _ = charger(ecrire_general(tmp_path))
    assert meteo_du_jour(JOUR, config, lambda adresse: corps) is None
    assert "météo indisponible" in capsys.readouterr().err


@pytest.mark.parametrize(("degres", "attendu"), [(359, "N"), (337.4, "NO"), (164, "S"), (0, "N")])
def test_directions(degres: float, attendu: str) -> None:
    donnees = {**REPONSE, "daily": {**REPONSE["daily"], "wind_direction_10m_dominant": [degres]}}
    assert lire_reponse(donnees, 20).direction == attendu


def test_lignes_en_anglais() -> None:
    assert ATTENDUE.lignes(EN) == [
        "18° → 26° · wind 29 km/h S",
        "Rain 38%, mostly in the evening",
        "Sun 7:40 → 19:26",
    ]
    ouest = Meteo(1, 2, 0, None, 10, "SO", "08:05", "17:00")
    assert ouest.lignes(EN) == ["1° → 2° · wind 10 km/h SW", "Rain 0%", "Sun 8:05 → 17:00"]
