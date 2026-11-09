"""La notion de demain (#126) : réservée la veille, présentée le lendemain, reportée en reprise.

La carte de démonstration est une chaîne (une seule notion débloquée à la fois) : on retire ses
prérequis pour avoir quatre racines, sinon rien ne serait à annoncer."""

import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from freinet.base import Base
from freinet.frontmatter import lire
from freinet.retour import noter
from tests.retour.scenario import LUNDI, passage, racine_demo
from tests.retour.scenario import plan as plan_par_secret


def _racine_sans_prerequis(tmp_path: Path) -> Path:
    racine = racine_demo(tmp_path)
    carte = racine / "bibliotheque" / "cartes" / "harmonie-demo.md"
    texte = carte.read_text(encoding="utf-8")
    debut, fin = texte.index("prerequis:"), texte.index("lateraux:")
    carte.write_text(texte[:debut] + "prerequis: []\n" + texte[fin:], encoding="utf-8")
    return racine


def _entete(racine: Path, jour: date) -> dict[str, object]:
    entete, _ = lire(racine / "brainiacs" / "marius" / "plans" / f"{jour.isoformat()}.md")
    return entete


def test_demain_annonce_puis_presente(tmp_path: Path) -> None:
    racine = _racine_sans_prerequis(tmp_path)
    passage(racine, LUNDI)
    lundi = _entete(racine, LUNDI)
    assert isinstance(lundi["demain"], str) and lundi["demain"] != lundi["nouvelle"]
    corps = (racine / "brainiacs" / "marius" / "plans" / f"{LUNDI.isoformat()}.md").read_text()
    assert "## À lire pour demain" in corps
    passage(racine, LUNDI + timedelta(days=1))
    assert _entete(racine, LUNDI + timedelta(days=1))["nouvelle"] == lundi["demain"]


def _noter_tout(racine: Path, jeton: str, jour: date) -> None:
    """Un scan : chaque question du ticket notée « Bien »."""
    p = plan_par_secret(racine, jeton)
    items = _entete(racine, jour)["items"]
    assert isinstance(items, list)
    quand = datetime(jour.year, jour.month, jour.day, 20, tzinfo=UTC)
    with Base(racine / "data" / "freinet.db") as base:
        for item in items:
            assert isinstance(item, dict)
            noter(base, racine, p, str(item["question_id"]), 3, quand)


def test_reprise_reporte_la_promesse(tmp_path: Path) -> None:
    """Sans scan, la reprise arrive (#11) : pas de notion nouvelle, la promesse reste annoncée ;
    au premier jour sans reprise, c'est elle qui est présentée."""
    racine = _racine_sans_prerequis(tmp_path)
    jours = [LUNDI + timedelta(days=n) for n in range(7)]
    promesse: object = None
    for jour in jours:
        acces = passage(racine, jour)
        entete = _entete(racine, jour)
        if entete["reprise"]:
            assert entete["nouvelle"] is None
            if promesse is not None:
                assert entete.get("demain") == promesse
            _noter_tout(racine, acces.jeton, jour)  # le scan qui fera sortir de la reprise
        elif promesse is not None:
            assert entete["nouvelle"] == promesse
        promesse = entete.get("demain")
    # Lundi présente une notion jamais notée : sans scan, la reprise arrive jeudi (#11, 3 jours).
    assert any(_entete(racine, j)["reprise"] for j in jours)


def test_douze_jours_la_promesse_est_toujours_tenue(tmp_path: Path) -> None:
    """Scans au hasard (graine fixe) : toute notion annoncée est présentée au premier jour sans
    reprise qui suit, et annoncée à nouveau par chaque jour de reprise entre les deux."""
    racine = _racine_sans_prerequis(tmp_path)
    hasard = random.Random(7)
    promesse: object = None
    for n in range(12):
        jour = LUNDI + timedelta(days=n)
        acces = passage(racine, jour)
        entete = _entete(racine, jour)
        if promesse is not None:
            if entete["reprise"]:
                assert entete.get("demain") == promesse
            else:
                assert entete["nouvelle"] == promesse
        if hasard.random() < 0.5:
            _noter_tout(racine, acces.jeton, jour)
        promesse = entete.get("demain")


def test_page_du_qr_donne_la_fiche_de_demain(tmp_path: Path) -> None:
    from freinet.bibliotheque import charger
    from freinet.retour import page

    racine = _racine_sans_prerequis(tmp_path)
    acces = passage(racine, LUNDI)
    promis = _entete(racine, LUNDI)["demain"]
    bib = charger(racine / "bibliotheque")
    with Base(racine / "data" / "freinet.db") as base:
        contenu = page(base, bib, racine, plan_par_secret(racine, acces.jeton))
    assert contenu.demain == (promis, bib.concepts[str(promis)].titre)
