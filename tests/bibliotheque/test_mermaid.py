from freinet.bibliotheque import charger
from freinet.contenu import Carte
from freinet.graphe import etats_maitrise
from freinet.mermaid import mermaid
from tests.bibliotheque.demo import DEMO

BIB = charger(DEMO)
CARTE = BIB.cartes["harmonie-demo"]
TITRES = {c.id: c.titre for c in BIB.concepts.values()}


def test_prerequis_pleins_lateraux_pointilles() -> None:
    texte = mermaid(CARTE, TITRES)
    assert texte.startswith("graph TD\n")
    assert '    accord_parfait["Accord parfait"]' in texte
    assert "    intervalle --> accord_parfait" in texte
    assert "    cadence_parfaite -. analogie .-> intervalle" in texte
    assert "classDef" not in texte


def test_couleurs_par_maitrise_et_guillemets_echappes() -> None:
    etats = etats_maitrise(CARTE, acquis={"intervalle"}, en_cours=set())
    texte = mermaid(CARTE, {**TITRES, "intervalle": 'Le "saut"'}, etats)
    assert '["Le #quot;saut#quot;"]' in texte
    assert "    class intervalle acquis" in texte
    assert "    class accord_parfait debloque" in texte
    assert "    class cadence_parfaite verrouille" in texte


def test_mot_reserve_mermaid_et_titre_multiligne() -> None:
    carte = Carte("k", ("end", "class-a"), (("end", "class-a"),), (), ())
    texte = mermaid(carte, {"end": "Fin\nde phrase", "class-a": "Classe A"})
    assert '    n_end["Fin de phrase"]' in texte
    assert "    n_end --> class_a" in texte
