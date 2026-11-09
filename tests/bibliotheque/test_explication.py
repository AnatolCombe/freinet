"""Le champ facultatif `explication` des questions : lu, puis contrôlé comme l'énoncé."""

from pathlib import Path

from freinet.bibliotheque import charger
from freinet.sources import lire_registre
from freinet.validation import erreurs_contenu
from tests.bibliotheque.demo import copie_demo

QUESTION = "questions/intervalle/intervalle-q1.md"


def _avec_explication(tmp_path: Path, explication: str) -> Path:
    racine = copie_demo(tmp_path)
    chemin = racine / QUESTION
    texte = chemin.read_text(encoding="utf-8")
    chemin.write_text(texte.replace("\n---", f"\nexplication: {explication!r}\n---", 1))
    return racine


def test_absente_vaut_vide(tmp_path: Path) -> None:
    bib = charger(copie_demo(tmp_path))
    assert bib.questions["intervalle-q1"].explication == ""


def test_lue(tmp_path: Path) -> None:
    racine = _avec_explication(tmp_path, "On compte les degrés, pas les demi-tons.")
    bib = charger(racine)
    assert bib.questions["intervalle-q1"].explication == "On compte les degrés, pas les demi-tons."
    assert not [p for p in erreurs_contenu(bib, lire_registre()) if "intervalle-q1" in p]


def test_lien_refuse(tmp_path: Path) -> None:
    bib = charger(_avec_explication(tmp_path, "Voir https://exemple.com"))
    problemes = erreurs_contenu(bib, lire_registre())
    assert any("lien ou balisage dans l'explication" in p for p in problemes)


def test_trop_longue(tmp_path: Path) -> None:
    bib = charger(_avec_explication(tmp_path, "mot " * 120))
    assert any("explication de" in p for p in erreurs_contenu(bib, lire_registre()))
