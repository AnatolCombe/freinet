"""L'espace d'un ticket : onglets, page du jour, Ma carte, liens qui restent dans l'espace."""

import re
from dataclasses import replace
from datetime import date

from freinet.espace import barre, page_de_lecture, page_du_jour, page_ma_carte
from freinet.libelles_espace import ESPACE_EN
from freinet.retour import NotionDeCarte, Page, QuestionANoter

ESPACE = "/r/jeton"
QUESTION = QuestionANoter(
    "intervalle-q1", "intervalle", "rappel", "Do-mi ?", 1, "Une tierce.",
    "On compte les degrés.", "Retiens : une tierce, trois degrés.",
    "Un intervalle mesure l'écart.\n\nRetiens : une tierce, trois degrés.",
)  # fmt: skip
CARTES = (("harmonie-demo", (NotionDeCarte("intervalle", "Intervalle", "en_cours"),)),)
PAGE = Page(date(2026, 10, 1), (QUESTION,), "Intervalle", False, (2, 5), "intervalle", CARTES)


def _jour(p: Page = PAGE) -> str:
    return page_du_jour(p, ESPACE).decode()


def _internes(corps: str) -> list[str]:
    return [h for h in re.findall(r"href='([^']*)'", corps) if not h.startswith("http")]


def test_rate_avec_explication() -> None:
    corps = _jour()
    assert "Jeudi 1 octobre 2026" in corps
    assert "<details><summary>Voir la réponse</summary><p>Une tierce.</p></details>" in corps
    assert "On compte les degrés." in corps and "Relire la fiche" not in corps
    assert "Notion du jour : <a href='/r/jeton/fiche/intervalle'>Intervalle</a>" in corps
    assert "<a href='/r/jeton/carte'>Voir ma carte</a>" in corps
    assert "Ta carte" not in corps  # la carte a son onglet


def test_rate_sans_explication() -> None:
    corps = _jour(replace(PAGE, questions=(replace(QUESTION, explication=""),)))
    assert "Retiens : une tierce, trois degrés." in corps
    assert "<a href='/r/jeton/fiche/intervalle'>Relire la fiche</a>" in corps


def test_reussi_sans_aide() -> None:
    corps = _jour(replace(PAGE, questions=(replace(QUESTION, note=3),)))
    assert "On compte les degrés." not in corps and "Relire la fiche" not in corps


def test_revoir_la_lecon() -> None:
    corps = _jour()
    assert "<summary>Revoir la leçon</summary><p>Un intervalle mesure l&#x27;écart.</p>" in corps
    assert "<a href='/r/jeton/fiche/intervalle'>Fiche complète</a>" in corps
    assert corps.index("<summary>Voir la réponse") < corps.index("<summary>Revoir la leçon")
    sans = _jour(replace(PAGE, questions=(replace(QUESTION, lecon=""),)))
    assert "<summary>Revoir la leçon" not in sans


def test_a_lire_pour_demain() -> None:
    corps = _jour(replace(PAGE, demain=("accord-parfait", "Accord parfait")))
    assert (
        "À lire pour demain : <a href='/r/jeton/fiche/accord-parfait'>Accord parfait</a>" in corps
    )
    assert corps.index("À lire pour demain") < corps.index("Notion du jour")


def test_barre() -> None:
    rendu = barre(ESPACE, "/carte")
    assert "<a href='/r/jeton'>Aujourd&#x27;hui</a>" in rendu
    assert "<a href='/r/jeton/carte' aria-current='page'>Ma carte</a>" in rendu
    assert "<a href='/r/jeton/cours'>Cours</a>" in rendu


def test_ma_carte() -> None:
    corps = page_ma_carte(PAGE, ESPACE).decode()
    assert "<h2><a href='/r/jeton/cours/harmonie-demo'>Harmonie demo</a></h2>" in corps
    assert "<span class='etat etat-en_cours'>en cours</span>" in corps
    assert "aria-current='page'>Ma carte</a>" in corps
    vide = page_ma_carte(replace(PAGE, cartes=()), ESPACE).decode()
    assert "Aucune carte suivie" in vide


def test_tout_reste_dans_l_espace() -> None:
    lecture = page_de_lecture("Fiche", "<p>x</p>", ESPACE).decode()
    assert "aria-current='page'>Cours</a>" in lecture
    for corps in (_jour(), page_ma_carte(PAGE, ESPACE).decode(), lecture):
        liens = _internes(corps)
        assert liens and all(h == ESPACE or h.startswith(ESPACE + "/") for h in liens)


def test_espace_en_anglais() -> None:
    en = replace(PAGE, noms_de_cartes=(("harmonie-demo", "Harmony demo"),))
    corps = page_du_jour(en, ESPACE, ESPACE_EN).decode()
    assert corps.startswith("<!doctype html><html lang='en'>")
    assert "<p class='surtitre'>Morning ticket</p><h1>Thursday 1 October 2026</h1>" in corps
    assert "Today's notion: <a href='/r/jeton/fiche/intervalle'>Intervalle</a>" in corps
    assert "1 · Missed" in corps and "Show the answer" in corps and "Question 1" in corps
    assert "This week: 2 ticket(s) rated out of 5." in corps
    assert ">Today</a>" in corps and ">Lessons</a>" in corps
    assert "I already know" in corps
    carte = page_ma_carte(en, ESPACE, ESPACE_EN).decode()
    assert "<h1>Where I stand</h1>" in carte and ">Harmony demo</a>" in carte
    assert "in progress" in carte
