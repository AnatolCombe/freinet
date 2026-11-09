from pathlib import Path

import pytest

from freinet.frontmatter import ErreurContenu, lire
from freinet.plan import plan_markdown
from freinet.rendu_png import png_ticket
from freinet.ticket import Reponse, lire_ticket, texte_ticket
from tests.ticket.demo import REFERENCE, RETOUR, comparer_reference, plan_couple
from tests.ticket.test_rendu_png import _empreinte


def test_ticket_du_couple_de_reference(tmp_path: Path, update_ref: bool) -> None:
    chemin, bib = plan_couple(tmp_path)
    ticket = lire_ticket(chemin, bib, RETOUR)
    comparer_reference("ticket-couple.txt", texte_ticket(ticket), update_ref)
    image = png_ticket(ticket)
    if update_ref:
        image.save(REFERENCE / "ticket-couple.png")  # à regarder ; le test compare l'empreinte
    comparer_reference("ticket-couple.png.sha256", _empreinte(image), update_ref)
    assert all(len(ligne) <= 48 for ligne in texte_ticket(ticket).splitlines())


def test_ordre_des_sections(tmp_path: Path) -> None:
    chemin, bib = plan_couple(tmp_path)
    titres = [b.texte for b in lire_ticket(chemin, bib).blocs if b.genre == "titre"]
    assert titres[:2] == ["Météo · Lyon", "Un mot de Marius"]
    assert titres[-4:] == [
        "Mot du jour · Allemand",
        "Ce jour-là · 6 janvier",
        "Énigme du mardi · Mots",
        "Notes",
    ]
    genres = [b.genre for b in lire_ticket(chemin, bib).blocs]
    assert genres.index("citation") < genres.index("separation") < genres.index("cadre")


def test_mot_de_seulement_sur_le_ticket_configure(tmp_path: Path) -> None:
    chemin, bib = plan_couple(tmp_path, "marius")
    texte = texte_ticket(lire_ticket(chemin, bib))
    assert "UN MOT DE" not in texte and texte.startswith("FREINET · MARIUS\n")
    chemin, bib = plan_couple(tmp_path / "elle")
    assert "UN MOT DE MARIUS" in texte_ticket(lire_ticket(chemin, bib))


def test_meteo_absente(tmp_path: Path) -> None:
    chemin, bib = plan_couple(tmp_path, meteo=None)
    texte = texte_ticket(lire_ticket(chemin, bib))
    assert "MÉTÉO" not in texte and "MOT DU JOUR · ALLEMAND" in texte
    entete, _ = lire(chemin)
    assert entete["general"] == {
        "mot": "waldeinsamkeit",
        "fait": "01-06",
        "enigme": "mots-1",
        "meteo": False,
    }


def test_meteo_figee_dans_le_plan(tmp_path: Path) -> None:
    chemin, bib = plan_couple(tmp_path)
    assert "Soleil 7 h 40 → 19 h 26" in chemin.read_text(encoding="utf-8")
    avant = chemin.read_bytes()
    assert plan_couple(tmp_path, meteo=None)[0] == chemin  # second passage, sans réseau
    assert chemin.read_bytes() == avant  # le plan écrit garde sa météo


def test_solution_dans_le_pli(tmp_path: Path) -> None:
    chemin, bib = plan_couple(tmp_path)
    assert lire_ticket(chemin, bib).reponses[-1] == Reponse("Énigme", "Solution mots 1.")


def test_sans_partie_le_plan_ne_change_pas(tmp_path: Path) -> None:
    from tests.ticket.demo import _bib_demo, _selection_demo

    bib = _bib_demo()
    s = _selection_demo(bib)
    assert plan_markdown(s, bib, "Allez.") == plan_markdown(s, bib, "Allez.", None)
    assert "séparation" not in plan_markdown(s, bib, "Allez.")


def test_partie_generale_en_anglais(tmp_path: Path) -> None:
    chemin, _ = plan_couple(tmp_path, langue="en")
    entete, corps = lire(chemin)
    assert entete["langue"] == "en"
    assert "## Weather · Lyon" in corps and "wind 29 km/h S" in corps
    assert "## A word from Marius\n\n[écrire : 2]" in corps
    assert "## Word of the day · German" in corps
    assert "## On this day · 6 January" in corps and "1412 : Joan of Arc" in corps
    assert "## Tuesday puzzle · Words" in corps and "## Notes" in corps


def test_ticket_anglais_de_reference(tmp_path: Path, update_ref: bool) -> None:
    chemin, bib = plan_couple(tmp_path, langue="en")
    ticket = lire_ticket(chemin, bib, RETOUR)
    comparer_reference("ticket-anglais.txt", texte_ticket(ticket), update_ref)
    png_ticket(ticket)  # le bitmap se dessine aussi


def test_ticket_anglais_reconnait_ses_sections(tmp_path: Path) -> None:
    chemin, bib = plan_couple(tmp_path, langue="en")
    ticket = lire_ticket(chemin, bib, RETOUR)
    genres = [b.genre for b in ticket.blocs]
    assert "question" in genres and "pre_test" in genres and "citation" in genres
    texte = texte_ticket(ticket)
    assert texte.startswith("FREINET · NOOR\nTuesday 6 January 2026\n")
    assert "RATE IT: scan the QR," in texte and "or type the code ABCD-EFGH at" in texte
    assert "✂ fold here" in texte and "\nANSWERS\n" in texte and "Before reading : " in texte
    assert ticket.reponses[-1].etiquette == "Puzzle"


def test_langue_inconnue_dans_le_plan(tmp_path: Path) -> None:
    chemin, bib = plan_couple(tmp_path)
    chemin.write_text(chemin.read_text(encoding="utf-8").replace("---\n", "---\nlangue: de\n", 1))
    with pytest.raises(ErreurContenu, match="langue"):
        lire_ticket(chemin, bib)
