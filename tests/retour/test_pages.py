"""Les pages de lecture sur la bibliothèque de démonstration (tests/donnees/bibliotheque)."""

import re
from pathlib import Path

import pytest

from freinet.bibliotheque import charger
from freinet.libelles_espace import ESPACE_EN
from freinet.pages import (
    PageInconnue,
    document,
    est_page_de_cours,
    page_de_cours,
    source_html,
)
from freinet.sources import lire_registre
from tests.bibliotheque.demo import DEMO, copie_demo, surcouche_en

REGISTRE = lire_registre()


def test_routes() -> None:
    for chemin in ["/", "/cours", "/cours/", "/cours/harmonie-demo", "/fiche/accord-parfait"]:
        assert est_page_de_cours(chemin), chemin
    for chemin in ["/r/abc", "/k/ABCD", "/c", "/fiche/", "/fiche/A_B", "/cours/x/y", "/fiche/../x"]:
        assert not est_page_de_cours(chemin), chemin


def test_sommaire_et_carte() -> None:
    bib = charger(DEMO)
    titre, corps = page_de_cours("/cours", bib, REGISTRE)
    assert titre == "Tous les cours"
    assert "href='/cours/harmonie-demo'" in corps and "4 notions" in corps
    _, corps = page_de_cours("/cours/harmonie-demo", bib, REGISTRE)
    assert corps.index("Intervalle") < corps.index("Cadence parfaite")  # ordre de la carte
    assert "Reconnaître une cadence parfaite à l&#x27;oreille" in corps  # la quête
    assert "href='/fiche/septieme-de-dominante'" in corps


def test_fiche_complete() -> None:
    titre, corps = page_de_cours("/fiche/cadence-parfaite", charger(DEMO), REGISTRE)
    assert titre == "Cadence parfaite"
    for attendu in [
        "<h1>Cadence parfaite</h1>",
        "<h2>Leçon</h2>",
        "<h2>Pour comprendre</h2>",
        "<h2>Analogies</h2>",
        "Rameau théorise la basse fondamentale",
        "Avant : <a href='/fiche/septieme-de-dominante'>Septième de dominante</a>",
        "Analogie : <a href='/fiche/intervalle'>Intervalle</a>",
    ]:
        assert attendu in corps, attendu
    # La source de l'anecdote (fr.wikipedia.org, registre culture.md) devient un lien.
    assert "rel='noopener noreferrer'" in corps and "target='_blank'" in corps


def test_fiche_par_alias() -> None:
    titre, _ = page_de_cours("/fiche/intervalles", charger(DEMO), REGISTRE)
    assert titre == "Intervalle"


def test_texte_echappe(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    chemin = racine / "concepts" / "intervalle.md"
    texte = chemin.read_text(encoding="utf-8")
    chemin.write_text(texte.replace("## Leçon\n\n", "## Leçon\n\n<script>alert(1)</script> "))
    _, corps = page_de_cours("/fiche/intervalle", charger(racine), REGISTRE)
    assert "<script>" not in corps and "&lt;script&gt;alert(1)&lt;/script&gt;" in corps


@pytest.mark.parametrize(
    ("reference", "titre", "lien"),
    [
        ("https://fr.wikipedia.org/wiki/Accord_parfait", "Accord", True),
        ("https://exemple.com/page", "", False),
        ("javascript://fr.wikipedia.org/%0aalert(1)", "", False),
        ("Jean-Philippe Rameau, Traité de l'harmonie (1722)", "", False),
    ],
)
def test_source_html(reference: str, titre: str, lien: bool) -> None:
    rendu = source_html(reference, titre, "musique", REGISTRE)
    assert ("<a " in rendu) is lien
    if lien:
        assert "rel='noopener noreferrer'" in rendu and ">Accord</a>" in rendu
    else:
        assert "href" not in rendu


def test_pages_inconnues() -> None:
    bib = charger(DEMO)
    for chemin in ["/cours/absente", "/fiche/absente", "/r/x"]:
        with pytest.raises(PageInconnue):
            page_de_cours(chemin, bib, REGISTRE)


def _internes(corps: str) -> list[str]:
    return [h for h in re.findall(r"href='([^']*)'", corps) if not h.startswith("http")]


def test_liens_prefixes() -> None:
    bib = charger(DEMO)
    for chemin in ["/cours", "/cours/harmonie-demo", "/fiche/cadence-parfaite"]:
        _, corps = page_de_cours(chemin, bib, REGISTRE, "/r/j")
        liens = _internes(corps)
        assert liens and all(h.startswith("/r/j/") for h in liens), chemin
    _, corps = page_de_cours("/fiche/cadence-parfaite", bib, REGISTRE)
    assert "href='/fiche/septieme-de-dominante'" in corps  # hors espace : inchangé


def test_document_tete() -> None:
    ouvert = document("T", "<p>x</p>").decode()
    assert "<a href='/c'>Mon ticket</a>" in ouvert and "<nav class='onglets'>" not in ouvert
    prive = document("T", "<p>x</p>", "/r/j", "<nav class='onglets'></nav>").decode()
    assert "<a class='marque' href='/r/j'>" in prive and "Mon ticket" not in prive
    assert prive.index("</main>") < prive.index("<nav class='onglets'>")
    assert "<body class=espace>" in prive


def test_pages_en_anglais(tmp_path: Path) -> None:
    racine = copie_demo(tmp_path)
    surcouche_en(racine)
    bib = charger(racine, "en")
    titre, corps = page_de_cours("/fiche/intervalle", bib, REGISTRE, "/r/x", ESPACE_EN)
    assert titre == "Interval"
    assert "<p class='surtitre'>Sheet · musique</p>" in corps
    assert "<h2>Lesson</h2>" in corps and "<h2>Neighbours</h2>" in corps
    assert "Harmony demo" in corps and "Avant" not in corps
    _, sommaire = page_de_cours("/cours", bib, REGISTRE, "/r/x", ESPACE_EN)
    assert "<h1>All lessons</h1>" in sommaire and "4 concepts" in sommaire
    _, carte = page_de_cours("/cours/harmonie-demo", bib, REGISTRE, "/r/x", ESPACE_EN)
    assert "<h1>Harmony demo</h1>" in carte and "<h2>Quests</h2>" in carte
    assert document("T", "<p>x</p>", "/r/x", "", "en").startswith(
        b"<!doctype html><html lang='en'>"
    )
