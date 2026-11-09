from pathlib import Path

import pytest

from freinet.dose import Dose, lire_dose
from freinet.frontmatter import ErreurContenu
from tests.bibliotheque.demo import ecrire


def test_dose_du_depot() -> None:
    assert lire_dose() == Dose(
        revisions=3,
        revisions_min=1,
        revisions_max=5,
        nouvelles=1,
        nouvelles_max=1,
        week_end=(0, 0, 100),
        reprise_jours=3,
    )


def test_bornes_de_dose() -> None:
    dose = lire_dose()
    assert [dose.borner_revisions(n) for n in (0, 3, 9)] == [1, 3, 5]


@pytest.mark.parametrize(
    ("revisions", "nouvelles", "message"),
    [
        ("| 9 | 1 – 5 |", "| 1 | 0 – 1 |", "hors de leurs bornes"),
        ("| 3 | 1 – 5 |", "| 2 | 0 – 2 |", "au plus 1"),
    ],
)
def test_dose_incoherente_refusee(
    tmp_path: Path, revisions: str, nouvelles: str, message: str
) -> None:
    fichier = tmp_path / "dose.md"
    ecrire(
        fichier,
        f"| révisions par ticket {revisions}\n| notions nouvelles par ticket {nouvelles}\n"
        "| dosage week-end (samedi, dimanche) | 0 / 0 / 100 (A2) | — |\n"
        "\nAprès ≥ 3 jours sans retour\n",
    )
    with pytest.raises(ErreurContenu, match=message):
        lire_dose(fichier)


def test_ligne_absente_refusee(tmp_path: Path) -> None:
    fichier = tmp_path / "dose.md"
    ecrire(fichier, "rien\n")
    with pytest.raises(ErreurContenu, match="révisions par ticket"):
        lire_dose(fichier)


def _dose(
    tmp_path: Path, revisions: str = "| 3 | 1 – 5 |", week_end: str = "0 / 0 / 100 (A2)"
) -> Path:
    fichier = tmp_path / "dose.md"
    ecrire(
        fichier,
        f"| **Révisions par ticket** {revisions}\n| notions nouvelles par ticket | 1 | 0 – 1 |\n"
        f"| dosage week-end (samedi, dimanche) | {week_end} | — |\n"
        "\nApres >= 4 jours sans retour\n",
    )
    return fichier


@pytest.mark.parametrize("revisions", ["| 3 (#9) | 1 à 5 |", "| 3 | 1-5 (#50) |", "| 3 | 1–5 |"])
def test_lecture_tolerante(tmp_path: Path, revisions: str) -> None:
    dose = lire_dose(_dose(tmp_path, revisions))
    assert (dose.revisions, dose.revisions_min, dose.revisions_max, dose.reprise_jours) == (
        3,
        1,
        5,
        4,
    )


@pytest.mark.parametrize(
    ("revisions", "week_end", "message"),
    [
        ("| 3 | 1 – 5 |", "0 / 100 (A2)", "trois parts"),
        ("| 3 | 1 – 5 |", "10 / 10 / 100", "trois parts"),
        ("| 3 | -1 – 5 |", "0 / 0 / 100", "bornes positives"),
        ("| 3 4 | 1 – 5 |", "0 / 0 / 100", "un défaut"),
    ],
)
def test_ligne_mal_formee_refusee(
    tmp_path: Path, revisions: str, week_end: str, message: str
) -> None:
    with pytest.raises(ErreurContenu, match=message):
        lire_dose(_dose(tmp_path, revisions, week_end))


def test_ligne_en_double_et_reprise_absente(tmp_path: Path) -> None:
    fichier = _dose(tmp_path)
    texte = fichier.read_text(encoding="utf-8")
    fichier.write_text(texte + "| révisions par ticket | 4 | 1 – 5 |\n", encoding="utf-8")
    with pytest.raises(ErreurContenu, match="en double"):
        lire_dose(fichier)
    fichier.write_text(texte.replace("Apres >= 4 jours", "Plus tard"), encoding="utf-8")
    with pytest.raises(ErreurContenu, match="seuil de reprise"):
        lire_dose(fichier)
