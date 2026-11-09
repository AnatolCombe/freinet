import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from freinet import quotidien
from freinet.base import Base
from freinet.bibliotheque import charger
from freinet.constantes import lire_regles
from freinet.etat import etat_coherent, recalculer
from freinet.frontmatter import lire
from freinet.rejeu import effectives
from freinet.retour import (
    OBJECTIF_SEMAINE,
    RetourRefuse,
    joker,
    langue_du_ticket,
    noter,
    page,
    retiens,
    verifier_delai,
)
from tests.retour.scenario import LUNDI, instant, passage, plan, racine_demo


def _heure(jour_offset: float) -> datetime:
    return datetime(2026, 1, 5, 7, tzinfo=UTC) + timedelta(days=jour_offset)


def _deux_jours(tmp_path: Path) -> tuple[Path, str]:
    """Lundi : la notion « intervalle » ; mardi : son premier rappel à noter."""
    racine = racine_demo(tmp_path)
    passage(racine, LUNDI)
    return racine, passage(racine, LUNDI + timedelta(days=1)).jeton


def test_page_du_ticket(tmp_path: Path) -> None:
    racine, jeton = _deux_jours(tmp_path)
    with Base(racine / "data" / "freinet.db") as base:
        contenu = page(base, charger(racine / "bibliotheque"), racine, plan(racine, jeton))
    assert [(q.question_id, q.nature, q.note) for q in contenu.questions] == [
        ("intervalle-q1", "rappel", None)
    ]
    assert contenu.semaine == (0, OBJECTIF_SEMAINE) and not contenu.joker


def test_une_note_une_fois_puis_une_correction(tmp_path: Path) -> None:
    racine, jeton = _deux_jours(tmp_path)
    p = plan(racine, jeton)
    with Base(racine / "data" / "freinet.db") as base:
        assert noter(base, racine, p, "intervalle-q1", 3, _heure(1)) == "notée"
        assert noter(base, racine, p, "intervalle-q1", 3, _heure(1.01)) == "inchangée"
        assert noter(base, racine, p, "intervalle-q1", 1, _heure(1.02)) == "corrigée"
        assert noter(base, racine, p, "intervalle-q1", 4, _heure(1.03)) == "corrigée"
        revues = [r for r in base.revues(p.brainiac_id) if r.plan_id == p.plan_id]
        assert len(revues) == 3  # l'origine et deux corrections : rien n'est effacé (inv. 3)
        assert [r.note for r in effectives(revues)] == [4]
        contenu = page(base, charger(racine / "bibliotheque"), racine, p)
        assert contenu.questions[0].note == 4 and contenu.semaine[0] == 1


def test_repondu_le_ramene_au_jour_du_ticket(tmp_path: Path) -> None:
    racine, jeton = _deux_jours(tmp_path)
    p = plan(racine, jeton)
    with Base(racine / "data" / "freinet.db") as base:
        noter(base, racine, p, "intervalle-q1", 3, _heure(3))  # noté jeudi, répondu mardi
        (r,) = [r for r in base.revues(p.brainiac_id) if r.plan_id == p.plan_id]
    assert r.repondu_le < datetime(2026, 1, 6, 23, tzinfo=UTC) and r.saisi_le == _heure(3)


@pytest.mark.parametrize(
    ("question", "note", "quand", "message"),
    [
        ("intervalle-q1", 5, 1, "note invalide"),
        ("accord-parfait-q1", 3, 1, "pas sur ce ticket"),
        ("intervalle-q1", 3, 9, "trop ancien"),
    ],
)
def test_retour_refuse(
    tmp_path: Path, question: str, note: int, quand: float, message: str
) -> None:
    racine, jeton = _deux_jours(tmp_path)
    with Base(racine / "data" / "freinet.db") as base, pytest.raises(RetourRefuse, match=message):
        noter(base, racine, plan(racine, jeton), question, note, _heure(quand))


def test_envois_simultanes_une_seule_note(tmp_path: Path) -> None:
    racine, jeton = _deux_jours(tmp_path)
    p = plan(racine, jeton)
    resultats: list[str] = []

    def envoyer() -> None:
        with Base(racine / "data" / "freinet.db") as base:
            resultats.append(noter(base, racine, p, "intervalle-q1", 3, _heure(1)))

    fils = [threading.Thread(target=envoyer) for _ in range(6)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()
    assert sorted(resultats) == ["inchangée"] * 5 + ["notée"]
    with Base(racine / "data" / "freinet.db") as base:
        assert len([r for r in base.revues(p.brainiac_id) if r.plan_id == p.plan_id]) == 1


def test_joker_donne_une_question_de_transfert_le_lendemain(tmp_path: Path) -> None:
    racine = racine_demo(tmp_path)
    acces = passage(racine, LUNDI)
    with Base(racine / "data" / "freinet.db") as base:
        joker(base, racine, plan(racine, acces.jeton), _heure(0))
        contenu = page(base, charger(racine / "bibliotheque"), racine, plan(racine, acces.jeton))
    assert contenu.joker and contenu.nouvelle == "Intervalle"
    arguments = [
        "--racine",
        str(racine),
        "--eleve",
        "marius",
        "--instant",
        instant(LUNDI + timedelta(days=1)),
    ]
    assert quotidien.main(arguments) == 0
    entete, _ = lire(racine / "brainiacs" / "marius" / "plans" / "2026-01-06.md")
    assert entete["items"] == [
        {"question_id": "intervalle-q2", "concept_id": "intervalle", "nature": "transfert"}
    ]


def test_joker_sans_notion_nouvelle(tmp_path: Path) -> None:
    racine, jeton = _deux_jours(tmp_path)
    with (
        Base(racine / "data" / "freinet.db") as base,
        pytest.raises(RetourRefuse, match="pas de notion"),
    ):
        joker(base, racine, plan(racine, jeton), _heure(1))


def test_le_plan_du_lendemain_reflete_le_retour(tmp_path: Path) -> None:
    """Critère V0 : le retour du QR se retrouve dans le ticket suivant."""
    resultats = {}
    for note in (1, 4):
        racine, jeton = _deux_jours(tmp_path / str(note))
        with Base(racine / "data" / "freinet.db") as base:
            noter(base, racine, plan(racine, jeton), "intervalle-q1", note, _heure(1))
        mercredi = instant(LUNDI + timedelta(days=2))
        assert (
            quotidien.main(["--racine", str(racine), "--eleve", "marius", "--instant", mercredi])
            == 0
        )
        entete, _ = lire(racine / "brainiacs" / "marius" / "plans" / "2026-01-07.md")
        resultats[note] = entete["items"]
    assert resultats[1] != resultats[4]  # raté : la question revient ; facile : elle s'espace


@pytest.mark.parametrize(
    ("quand", "admis"),
    [
        (datetime(2026, 1, 13, 22, 59, tzinfo=UTC), True),  # J+7, 23:59 à Paris
        (datetime(2026, 1, 13, 23, 1, tzinfo=UTC), False),  # J+8, 00:01 à Paris
        (datetime(2026, 1, 5, 7, tzinfo=UTC), False),  # la veille : ticket pas encore arrivé
    ],
)
def test_fenetre_de_notation(tmp_path: Path, quand: datetime, admis: bool) -> None:
    racine, jeton = _deux_jours(tmp_path)
    with Base(racine / "data" / "freinet.db") as base:
        if admis:
            assert noter(base, racine, plan(racine, jeton), "intervalle-q1", 3, quand) == "notée"
        else:
            with pytest.raises(RetourRefuse, match="trop ancien|pas encore arrivé"):
                noter(base, racine, plan(racine, jeton), "intervalle-q1", 3, quand)


def test_corrections_simultanees_puis_rejeu_identique(tmp_path: Path) -> None:
    racine, jeton = _deux_jours(tmp_path)
    p = plan(racine, jeton)
    with Base(racine / "data" / "freinet.db") as base:
        noter(base, racine, p, "intervalle-q1", 3, _heure(1))

    def corriger(note: int) -> None:
        with Base(racine / "data" / "freinet.db") as base:
            noter(base, racine, p, "intervalle-q1", note, _heure(1.1))

    fils = [threading.Thread(target=corriger, args=(n,)) for n in (1, 2, 4, 1, 2, 4)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()
    with Base(racine / "data" / "freinet.db") as base:
        revues = [r for r in base.revues(p.brainiac_id) if r.plan_id == p.plan_id]
        assert len({r.revue_id for r in revues}) == len(revues)  # aucune collision
        assert len(effectives(revues)) == 1
        regles = lire_regles()
        bib = charger(racine / "bibliotheque")
        recalculer(base, p.brainiac_id, regles, bib.canonique)
        assert etat_coherent(base, p.brainiac_id, regles, bib.canonique)  # inv. 4


def test_retiens() -> None:
    assert retiens("Un problème ? Voilà. Retiens : l'idée simple.") == "Retiens : l'idée simple."
    assert retiens("Sans phrase finale.") == "Sans phrase finale."


def test_page_enrichie(tmp_path: Path) -> None:
    racine, jeton = _deux_jours(tmp_path)
    bib = charger(racine / "bibliotheque")
    with Base(racine / "data" / "freinet.db") as base:
        contenu = page(base, bib, racine, plan(racine, jeton))
    (question,) = contenu.questions
    assert question.reponse == bib.questions["intervalle-q1"].reponse
    assert question.explication == ""
    assert question.retiens == bib.concepts["intervalle"].lecon  # la démo n'a pas de « Retiens »
    assert question.lecon == bib.concepts["intervalle"].lecon
    ((carte_id, notions),) = contenu.cartes
    assert carte_id == "harmonie-demo"
    etats = {n.concept_id: n.etat for n in notions}
    assert etats["intervalle"] == "en_cours"  # présentée lundi
    assert etats["cadence-parfaite"] == "verrouille"
    assert [n.concept_id for n in notions] == list(bib.cartes["harmonie-demo"].concepts)


def test_retiens_dans_la_langue() -> None:
    from freinet.langue import EN

    assert retiens("Bla. Remember: count both ends.", EN) == "Remember: count both ends."
    assert retiens("Bla. Retiens : compte.") == "Retiens : compte."


def test_langue_du_ticket(tmp_path: Path) -> None:
    racine = racine_demo(tmp_path)
    acces = passage(racine, LUNDI)
    trouve = plan(racine, acces.jeton)
    with Base(racine / "data" / "freinet.db") as base:
        assert langue_du_ticket(base, racine, trouve) == "fr"
        chemin = racine / "brainiacs" / "marius" / "plans" / "2026-01-05.md"
        chemin.write_text(
            chemin.read_text(encoding="utf-8").replace("---\n", "---\nlangue: en\n", 1),
            encoding="utf-8",
        )
        assert langue_du_ticket(base, racine, trouve) == "en"
        page_en = page(base, charger(racine / "bibliotheque", "en"), racine, trouve, "en")
        assert dict(page_en.noms_de_cartes) == {"harmonie-demo": "Harmonie demo"}


def test_fenetre_du_qr() -> None:
    mardi = date(2026, 1, 6)
    verifier_delai(mardi, mardi)  # le jour même
    verifier_delai(date(2025, 12, 30), mardi)  # 7 jours après : encore admis
    with pytest.raises(RetourRefuse, match="2025-12-29 : trop ancien"):
        verifier_delai(date(2025, 12, 29), mardi)
    with pytest.raises(RetourRefuse, match="2026-01-07 : pas encore arrivé"):
        verifier_delai(date(2026, 1, 7), mardi)
