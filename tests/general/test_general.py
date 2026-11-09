import re
from pathlib import Path
from typing import Any

import pytest

from freinet import general
from freinet.frontmatter import ErreurContenu
from freinet.general import Profil, lire_config, lire_listes
from tests.general.listes import (
    CONFIG,
    CONFIG_EN,
    ENIGMES,
    LANGUES_EN,
    MOTS,
    charger,
    ecrire_general,
    faits,
)


def test_lecture(tmp_path: Path) -> None:
    config, listes = charger(ecrire_general(tmp_path))
    assert config.profil("noor") == Profil("NOOR", "Marius")
    assert config.profil("marius") == Profil("MARIUS")
    assert config.profil("alice") == Profil("ALICE")  # élève hors config : prénom = nom
    assert config.langues[-1] == "hébreu" and config.seuil_pluie == 20
    assert len(listes.faits) == 366 and listes.faits["02-29"].annee == 1900
    assert [m.id for m in listes.mots][:2] == ["dor", "waldeinsamkeit"]


def _sans(cle: str) -> dict[str, object]:
    return {k: v for k, v in CONFIG.items() if k != cle}


@pytest.mark.parametrize(
    ("remplacement", "message"),
    [
        ({"mots": [{**MOTS[0], "langue": "latin"}, *MOTS[1:]]}, "hors de la rotation"),
        ({"mots": [{**MOTS[4], "forme": "שָׁלוֹם"}, *MOTS[:4]]}, "niqqud"),
        ({"mots": [{**MOTS[0], "source": ""}, *MOTS[1:]]}, "« source » vide ou absent"),
        ({"mots": [{**MOTS[0], "sens": "Un sourire 😀"}, *MOTS[1:]]}, "non imprimables"),
        ({"mots": [{**MOTS[0], "sens": "## Faux titre"}, *MOTS[1:]]}, "syntaxe du plan"),
        ({"faits": [{**faits()[0], "texte": "> Citation."}, *faits()[1:]]}, "syntaxe du plan"),
        ({"enigmes": [{**ENIGMES[0], "enonce": "[cadre : 3]"}, *ENIGMES[1:]]}, "syntaxe du plan"),
        ({"mots": [{**MOTS[0], "sens": "x" * 97}, *MOTS[1:]]}, "trop long"),
        ({"mots": MOTS[:4]}, "aucun mot pour : hébreu"),
        ({"mots": [*MOTS, MOTS[0]]}, "en double : dor"),
        ({"mots": {"pas": "une liste"}}, "liste « mots »"),
        ({"faits": faits()[1:]}, "1 jour(s) sans fait, dont 01-01"),
        ({"faits": [*faits(), {**faits()[0]}]}, "01-01 en double"),
        ({"faits": [{**faits()[0], "jour": "13-01"}, *faits()[1:]]}, "MM-JJ"),
        ({"faits": [{**faits()[0], "annee": "jadis"}, *faits()[1:]]}, "année"),
        ({"faits": [{**faits()[0], "annee": 1900}, *faits()[1:]]}, "année entre guillemets"),
        ({"faits": [{**faits()[0], "annee": "0476"}, *faits()[1:]]}, "année entre guillemets"),
        ({"faits": [{**faits()[0], "texte": "x" * 97}, *faits()[1:]]}, "trop long (> 96)"),
        ({"mots": [MOTS[0], "texte"]}, "liste « mots », entrée n° 2 : table attendue"),
        ({"mots": [{k: v for k, v in MOTS[0].items() if k != "id"}, *MOTS[1:]]}, "entrée n° 1"),
        ({"enigmes": [{**ENIGMES[0], "solution": "x" * 97}, *ENIGMES[1:]]}, "trop long (> 96)"),
        ({"enigmes": [{**ENIGMES[0], "enonce": "x" * 201}, *ENIGMES[1:]]}, "trop long (> 200)"),
        ({"config": _sans("eleves")}, "« eleves » : table nom"),
        (
            {"config": {**CONFIG, "eleves": {"a": {"prenom": 12}}}},
            "« prenom » / « mot_de » en texte",
        ),
        ({"config": {**CONFIG, "eleves": {"a": {"prenom": "A", "mot_de": 3}}}}, "en texte attendu"),
        ({"config": {**CONFIG, "fuseau": "Mars/Olympus"}}, "fuseau inconnu"),
        ({"config": {**CONFIG, "fuseau": "Europe"}}, "fuseau inconnu"),  # un dossier de tzdata
        ({"config": {**CONFIG, "langues": ["roumain", "roumain"]}}, "langue en double"),
        ({"config": {**CONFIG, "ville": "Ville 😀"}}, "config : caractères non imprimables"),
        ({"enigmes": [{**ENIGMES[0], "type": "devinette"}, *ENIGMES[1:]]}, "type « devinette »"),
        ({"enigmes": ENIGMES[:4]}, "aucune énigme de type : chiffres"),
        ({"config": {**CONFIG, "origine": "demain"}}, "origine"),
        ({"config": {**CONFIG, "langues": []}}, "« langues »"),
        ({"config": {**CONFIG, "seuil_pluie": 140}}, "seuil"),
        ({"config": _sans("ville")}, "« ville »"),
        ({"config": {**CONFIG, "eleves": {"noor": {"mot_de": "Marius"}}}}, "« prenom »"),
    ],
)
def test_factory_invalide(tmp_path: Path, remplacement: dict[str, Any], message: str) -> None:
    with pytest.raises(ErreurContenu, match=re.escape(message)):
        charger(ecrire_general(tmp_path, **remplacement))


def test_bilan_en_ligne_de_commande(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert general.main(["--dossier", str(ecrire_general(tmp_path / "ok"))]) == 0
    sortie = capsys.readouterr().out
    assert "mots 6 (roumain 2, allemand 1, anglais 1, espagnol 1, hébreu 1)" in sortie
    assert "faits 366" in sortie and "énigmes 6 (logique 2, mots 2, chiffres 2)" in sortie
    assert general.main(["--dossier", str(ecrire_general(tmp_path / "ko", mots=[]))]) == 1
    assert "aucun mot pour" in capsys.readouterr().err


def test_profil_en_francais_par_defaut(tmp_path: Path) -> None:
    config, listes = charger(ecrire_general(tmp_path))
    assert config.profil("marius").langue == "fr" and config.profil("inconnu").langue == "fr"
    assert listes.rotation == config.langues and config.langues_en == ()


def test_listes_anglaises(tmp_path: Path) -> None:
    config, listes = charger(ecrire_general(tmp_path, en=True), "en")
    assert config.profil("noor").langue == "en"
    assert config.langues_en == tuple(LANGUES_EN) and listes.rotation == tuple(LANGUES_EN)
    assert {m.langue for m in listes.mots} == set(LANGUES_EN)
    assert listes.faits["01-06"].texte.startswith("Joan of Arc")


def test_langue_inconnue_refusee(tmp_path: Path) -> None:
    eleves = {"noor": {"prenom": "NOOR", "langue": "de"}}
    with pytest.raises(ErreurContenu, match="langue inconnue"):
        charger(ecrire_general(tmp_path, config={**CONFIG_EN, "eleves": eleves}))


def test_eleve_anglais_sans_rotation_anglaise(tmp_path: Path) -> None:
    config = {k: v for k, v in CONFIG_EN.items() if k != "langues_en"}
    with pytest.raises(ErreurContenu, match="langues_en"):
        charger(ecrire_general(tmp_path, config=config))


def test_rotation_anglaise_au_meme_rang(tmp_path: Path) -> None:
    config = {**CONFIG_EN, "langues_en": LANGUES_EN[:4]}
    with pytest.raises(ErreurContenu, match="même nombre de langues"):
        charger(ecrire_general(tmp_path, config=config))


def test_listes_anglaises_absentes(tmp_path: Path) -> None:
    dossier = ecrire_general(tmp_path, config=CONFIG_EN)  # config anglaise, pas de en/
    config = lire_config(dossier / "general.md")
    with pytest.raises(OSError):
        lire_listes(config, dossier, "en")


def test_rotation_d_une_langue_sans_rotation(tmp_path: Path) -> None:
    config, _ = charger(ecrire_general(tmp_path))
    with pytest.raises(ValueError, match="langues_en"):
        config.rotation("en")
