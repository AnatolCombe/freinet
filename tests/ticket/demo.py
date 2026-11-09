"""Un plan de démonstration complet : révision, notion nouvelle avec pré-test, anecdote."""

from dataclasses import replace
from pathlib import Path

from freinet.bibliotheque import Bibliotheque
from freinet.langue import libelles
from freinet.meteo import Meteo
from freinet.partie_generale import partie_du_jour
from freinet.plan import ecrire_plan
from freinet.selection import Item, Nouvelle, Selection
from freinet.ticket import Retour
from tests.general.listes import charger, ecrire_general
from tests.selection.scenario import BIB, reponse, selection

REFERENCE = Path(__file__).parent / "reference"
RETOUR = Retour(
    "http://freinet.local:8765/r/0123456789abcdef0123456789abcdef",
    "ABCD-EFGH",
    "freinet.local:8765/c",
)


def _bib_demo() -> Bibliotheque:
    pre_test = replace(
        BIB.questions["accord-parfait-q1"], id="accord-parfait-q9", nature="pre_test"
    )
    return replace(BIB, questions={**BIB.questions, pre_test.id: pre_test})


def _selection_demo(bib: Bibliotheque) -> Selection:
    pre_test = bib.questions["accord-parfait-q9"]
    s = selection([reponse(1, "intervalle-q1", 1, 0)], 1)  # une révision due le 6 janvier
    concept = bib.concepts["accord-parfait"]
    item = Item(concept.id, pre_test.id, pre_test.nature, pre_test.enonce)
    return replace(s, nouvelle=Nouvelle(concept.id, concept.titre, concept.lecon, item))


def plan_demo(dossier: Path) -> tuple[Path, Bibliotheque]:
    bib = _bib_demo()
    return ecrire_plan(_selection_demo(bib), bib, dossier, "Un pas de plus aujourd'hui."), bib


METEO = Meteo(18, 26, 38, "le soir", 29, "S", "07:40", "19:26")


def plan_couple(
    dossier: Path, nom: str = "noor", meteo: Meteo | None = METEO, langue: str = "fr"
) -> tuple[Path, Bibliotheque]:
    """Le plan de démonstration (mardi 6 janvier 2026) avec la partie générale de test :
    allemand (waldeinsamkeit), énigme de mots, Jeanne d'Arc ; `langue="en"` : listes et
    libellés anglais."""
    bib = _bib_demo()
    s = _selection_demo(bib)
    config, listes = charger(ecrire_general(dossier / "general", en=langue == "en"), langue)
    partie = partie_du_jour(nom, s.jour, config, listes, meteo)
    phrase = libelles(langue).phrase_defaut
    return ecrire_plan(s, bib, dossier / nom, phrase, partie, langue=langue), bib


def comparer_reference(nom: str, contenu: str, mettre_a_jour: bool) -> None:
    """Compare à `reference/<nom>` ; `pytest --update-ref` la réécrit (#33)."""
    chemin = REFERENCE / nom
    if mettre_a_jour:
        chemin.write_text(contenu, encoding="utf-8")
    assert chemin.read_text(encoding="utf-8") == contenu, (
        f"{nom} a changé : relire le rendu, puis `pytest --update-ref` si c'est voulu"
    )
