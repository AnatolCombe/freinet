from freinet.contenu import Carte, Lateral
from freinet.graphe import erreurs_carte, etats_maitrise, ordre_deblocage

CONNUS = {"a", "b", "c", "d"}


def _carte(
    concepts: tuple[str, ...] = ("a", "b", "c"),
    prerequis: tuple[tuple[str, str], ...] = (("a", "b"), ("b", "c")),
    lateraux: tuple[Lateral, ...] = (),
) -> Carte:
    return Carte("k", concepts, prerequis, lateraux, ())


def test_carte_valide() -> None:
    assert erreurs_carte(_carte(), CONNUS) == []


def test_cycle_refuse() -> None:
    carte = _carte(prerequis=(("a", "b"), ("b", "c"), ("c", "a")))
    assert erreurs_carte(carte, CONNUS) == ["k : cycle de prérequis a → b → c → a"]


def test_orphelin_inconnu_hors_carte_et_doublon_refuses() -> None:
    carte = _carte(
        concepts=("a", "b", "c", "d", "zz", "a"),
        prerequis=(("a", "b"), ("b", "c"), ("c", "x")),
        lateraux=(Lateral("a", "a", "analogie"),),
    )
    erreurs = erreurs_carte(carte, CONNUS)
    attendus = [
        "concept a listé 2 fois",
        "concept inconnu zz",
        "hors carte (x)",
        "lien latéral de a vers lui-même",
        "concept orphelin d",
    ]
    for attendu in attendus:
        assert any(attendu in e for e in erreurs), attendu


def test_lateral_hors_carte_et_boucle_de_prerequis() -> None:
    carte = _carte(
        prerequis=(("a", "a"), ("a", "b"), ("b", "c")), lateraux=(Lateral("a", "x", "contraste"),)
    )
    erreurs = erreurs_carte(carte, CONNUS)
    assert any("a est son propre prérequis" in e for e in erreurs)
    assert any("lien latéral a ~ x hors carte" in e for e in erreurs)


def test_concept_seul_n_est_pas_orphelin() -> None:
    assert erreurs_carte(_carte(concepts=("a",), prerequis=()), CONNUS) == []


def test_ordre_deblocage_deterministe() -> None:
    carte = _carte(concepts=("c", "b", "a", "d"), prerequis=(("a", "c"), ("b", "c"), ("c", "d")))
    assert ordre_deblocage(carte) == ["a", "b", "c", "d"]


def test_etats_maitrise() -> None:
    etats = etats_maitrise(_carte(), acquis={"a"}, en_cours={"c"})
    assert etats == {"a": "acquis", "b": "debloque", "c": "en_cours"}
    assert etats_maitrise(_carte(), acquis=set(), en_cours=set())["b"] == "verrouille"


def test_acquis_reste_acquis_et_tous_les_prerequis_requis() -> None:
    carte = _carte(concepts=("a", "b", "c"), prerequis=(("a", "c"), ("b", "c")))
    assert etats_maitrise(carte, acquis={"a"}, en_cours=set())["c"] == "verrouille"
    assert etats_maitrise(carte, acquis={"a", "b"}, en_cours=set())["c"] == "debloque"
    assert etats_maitrise(_carte(), acquis={"c"}, en_cours=set())["c"] == "acquis"


def test_extremite_hors_carte_ignoree_par_l_ordre() -> None:
    carte = _carte(prerequis=(("x", "a"), ("a", "b"), ("b", "c")))
    assert ordre_deblocage(carte) == ["a", "b", "c"]
