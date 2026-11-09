from dataclasses import replace
from pathlib import Path

from freinet.bibliotheque import Bibliotheque
from freinet.rendu_png import png_ticket
from freinet.ticket import LIGNES_MAX, Bloc, Reponse, lire_ticket, texte_ticket
from tests.ticket.demo import plan_demo


def _plan(dossier: Path, corps: str, entete: str = "") -> Path:
    chemin = dossier / "plan.md"
    chemin.write_text(
        f"---\ntype: plan\njour: '2026-01-05'\n{entete}---\n\n# Plan\n\n{corps}", "utf-8"
    )
    return chemin


def _bib(dossier: Path) -> Bibliotheque:
    return plan_demo(dossier / "bib")[1]


def test_marques_d_ecriture_et_separation(tmp_path: Path) -> None:
    corps = (
        "## Un mot de Marius\n\n[écrire : 2]\n\n> Allez.\n\nSuite du jour.\n\n"
        "[séparation]\n\n## Notes\n\n[cadre : 5]\n"
    )
    ticket = lire_ticket(_plan(tmp_path, corps), _bib(tmp_path))
    assert ticket.blocs == (
        Bloc("titre", "Un mot de Marius"),
        Bloc("ecrire", "écrire", 2),
        Bloc("citation", "Allez."),
        Bloc("texte", "Suite du jour."),
        Bloc("separation", "séparation"),
        Bloc("titre", "Notes"),
        Bloc("cadre", "cadre", 5),
    )
    texte = texte_ticket(ticket)
    assert texte.count(". " * 23 + ".") == 2
    assert "┌" + "─" * 46 + "┐" in texte
    assert texte.count("│" + " " * 46 + "│") == 5
    assert all(len(ligne) <= 48 for ligne in texte.splitlines())


def test_citation_apres_la_meteo_mais_pas_dans_une_section(tmp_path: Path) -> None:
    corps = "## Météo · Ici\n\n18° → 26°\n\n> Allez.\n\n## Révisions\n\n> pas une citation\n"
    ticket = lire_ticket(_plan(tmp_path, corps), _bib(tmp_path))
    assert [b.genre for b in ticket.blocs] == ["titre", "texte", "citation", "titre", "texte"]


def test_marque_bornee_ou_ignoree(tmp_path: Path) -> None:
    corps = "[cadre : 99]\n\n[cadre : 0]\n"
    ticket = lire_ticket(_plan(tmp_path, corps), _bib(tmp_path))
    assert ticket.blocs == (Bloc("cadre", "cadre", LIGNES_MAX), Bloc("texte", "[cadre : 0]"))


def test_prenom_et_solution_de_l_enigme(tmp_path: Path) -> None:
    entete = "prenom: NOOR\nsolution_enigme: '33 (chaque écart double).'\n"
    ticket = lire_ticket(_plan(tmp_path, "> Allez.\n", entete), _bib(tmp_path))
    assert ticket.prenom == "NOOR"
    assert ticket.reponses == (Reponse("Énigme", "33 (chaque écart double)."),)
    lignes = texte_ticket(ticket).splitlines()
    assert lignes[:3] == ["FREINET · NOOR", "lundi 5 janvier 2026", "=" * 48]
    assert "Énigme : 33 (chaque écart double)." in lignes


def test_sans_prenom_l_en_tete_ne_change_pas(tmp_path: Path) -> None:
    ticket = lire_ticket(_plan(tmp_path, "> Allez.\n"), _bib(tmp_path))
    assert ticket.prenom is None
    assert texte_ticket(ticket).splitlines()[0] == "FREINET · lundi 5 janvier 2026"


def test_png_des_marques_et_du_prenom(tmp_path: Path) -> None:
    corps = "## Un mot de Marius\n\n[écrire : 2]\n\n> Allez.\n\n[séparation]\n\n[cadre : 5]\n"
    ticket = lire_ticket(_plan(tmp_path, corps, "prenom: NOOR\n"), _bib(tmp_path))
    image = png_ticket(ticket)
    assert image.tobytes() != png_ticket(replace(ticket, prenom=None)).tobytes()
    court = replace(ticket, blocs=tuple(b for b in ticket.blocs if b.genre != "cadre"))
    assert png_ticket(court).height + 5 * 40 <= image.height  # le cadre prend ses 5 lignes
