from dataclasses import replace
from pathlib import Path

import pytest

from freinet.frontmatter import ErreurContenu
from freinet.rendu_png import png_ticket
from freinet.ticket import (
    Bloc,
    Reponse,
    barre,
    date_longue,
    lire_ticket,
    propre,
    source_lisible,
    texte_ticket,
)
from tests.ticket.demo import RETOUR, comparer_reference, plan_demo


def test_ticket_de_reference(tmp_path: Path, update_ref: bool) -> None:
    chemin, bib = plan_demo(tmp_path)
    ticket = lire_ticket(chemin, bib, RETOUR)
    comparer_reference("ticket-demo.txt", texte_ticket(ticket), update_ref)
    assert ticket.reponses == (
        Reponse("1", propre(bib.questions["intervalle-q2"].reponse)),
        Reponse("Avant de lire", propre(bib.questions["accord-parfait-q9"].reponse)),
    )
    assert Bloc("source", "Source : fr.wikipedia.org") in ticket.blocs  # hôte seul (#45)
    assert all(len(ligne) <= 48 for ligne in texte_ticket(ticket).splitlines())
    assert "0123456789abcdef" not in texte_ticket(ticket)  # le jeton n'est que dans le QR


def test_le_plan_fait_foi(tmp_path: Path) -> None:
    chemin, bib = plan_demo(tmp_path)
    texte = chemin.read_text(encoding="utf-8")
    chemin.write_text(texte.replace("Un pas de plus", "Un grand pas"), encoding="utf-8")
    assert Bloc("citation", "Un grand pas aujourd'hui.") in lire_ticket(chemin, bib).blocs


def test_question_retiree_de_la_bibliotheque(tmp_path: Path) -> None:
    chemin, bib = plan_demo(tmp_path)
    texte = chemin.read_text(encoding="utf-8")
    chemin.write_text(texte.replace("question_id: intervalle-q2", "question_id: disparue"), "utf-8")
    ticket = lire_ticket(chemin, bib)
    assert [r.etiquette for r in ticket.reponses] == ["Avant de lire"]
    assert "NOTER" not in texte_ticket(ticket)


def test_plan_sans_items_ni_pli(tmp_path: Path) -> None:
    chemin = tmp_path / "plan.md"
    chemin.write_text("---\ntype: plan\njour: '2026-01-05'\n---\n\n# Plan\n\n> Allez.\n", "utf-8")
    chemin_bib, bib = plan_demo(tmp_path / "autre")
    ticket = lire_ticket(chemin, bib)
    assert ticket.blocs == (Bloc("citation", "Allez."),) and ticket.reponses == ()
    assert "RÉPONSES" not in texte_ticket(ticket)


def test_jour_invalide(tmp_path: Path) -> None:
    chemin = tmp_path / "plan.md"
    chemin.write_text("---\ntype: plan\njour: demain\n---\n", encoding="utf-8")
    with pytest.raises(ErreurContenu, match="jour invalide"):
        lire_ticket(chemin, plan_demo(tmp_path / "autre")[1])


def test_textes_nettoyes() -> None:
    assert propre("a\x1b@b\u200bc\td\n") == "a @b c d"  # ESC ne pilote pas l'imprimante
    assert propre("Quoi\u202f? anti\u00adconstitu\u00adtionnel e\u0301") == (
        "Quoi\u202f? anticonstitutionnel é"  # insécable gardée, trait conditionnel retiré, NFC
    )
    assert source_lisible("https://www.example.org/x?jeton=1") == "example.org"
    assert source_lisible("https:///chemin?jeton=secret") == "source web"
    assert source_lisible("https://fr.wiki\x1bpedia.org/") == "fr.wiki pedia.org"
    assert source_lisible("Rameau, Traité de l'harmonie (1722)") == (
        "Rameau, Traité de l'harmonie (1722)"
    )
    assert source_lisible("javascript:alert(1)\x07") == "javascript:alert(1)"


def test_barre_et_date() -> None:
    assert barre(1, 4, 8) == "▓▓░░░░░░ 1/4"
    assert barre(9, 4, 4) == "▓▓▓▓ 9/4" and barre(0, 0, 4) == "░░░░ 0/0"
    assert date_longue(__import__("datetime").date(2026, 8, 15)) == "samedi 15 août 2026"


def _plan(tmp_path: Path, corps: str) -> Path:
    chemin = tmp_path / "plan.md"
    chemin.write_text(f"---\ntype: plan\njour: '2026-01-05'\n---\n\n{corps}", encoding="utf-8")
    return chemin


def test_questions_reconnues_seulement_a_leur_place(tmp_path: Path) -> None:
    bib = plan_demo(tmp_path / "demo")[1]
    corps = (
        "> Allez.\n\n## Nouveau · Chant\n\n1. écoute\n2. chante\n\n"
        "## Révisions\n\n1. Vraie question ?\n\n> citation dans une section\n\n"
        "## Défi du jour\n\nAvant de lire : pas ici\n\n> \u200b\n"
    )
    ticket = lire_ticket(_plan(tmp_path, corps), bib)
    assert [b.genre for b in ticket.blocs] == [
        "citation",
        "titre",
        "texte",
        "titre",
        "question",
        "texte",
        "titre",
        "texte",
        "texte",
    ]
    assert ticket.blocs[2].texte == "1. écoute 2. chante"  # une leçon en étapes reste du texte
    assert ticket.blocs[-1] == Bloc("texte", ">")  # une citation vide ne plante pas le rendu
    png_ticket(ticket)


def test_avertissement_finance_sur_le_ticket(tmp_path: Path) -> None:
    chemin, bib = plan_demo(tmp_path)
    finance = replace(bib.concepts["accord-parfait"], domaine="finance")
    avertissement = Bloc("avertissement", "Éducatif, pas un conseil d'investissement.")
    assert (
        lire_ticket(chemin, replace(bib, concepts={**bib.concepts, finance.id: finance})).blocs[-1]
        == avertissement
    )
    assert avertissement not in lire_ticket(chemin, bib).blocs
    png_ticket(lire_ticket(chemin, replace(bib, concepts={**bib.concepts, finance.id: finance})))
