from dataclasses import replace

from fsrs import Card

from freinet.acquis import regle_satisfaite
from freinet.constantes import lire_regles
from freinet.planification import carte_neuve, reviser
from tests.socle.fabrique import T0

REGLES = lire_regles()


def _trois_revues_reussies() -> Card:
    """Trois « Bien » aux échéances FSRS (J0, J2, J13) : stabilité ~46 j, soit ~0,93 à J+30."""
    carte, quand = carte_neuve(T0), T0
    for _ in range(3):
        carte = reviser(carte, 3, quand)
        quand = carte.due
    return carte


def test_carte_jamais_revisee_jamais_acquise() -> None:
    assert not regle_satisfaite(carte_neuve(T0), transferts_reussis=1, regles=REGLES)


def test_une_seule_revue_ne_suffit_pas() -> None:
    carte = reviser(carte_neuve(T0), 3, T0)
    assert not regle_satisfaite(carte, transferts_reussis=1, regles=REGLES)


def test_memoire_durable_et_transfert_donnent_acquis() -> None:
    assert regle_satisfaite(_trois_revues_reussies(), transferts_reussis=1, regles=REGLES)


def test_sans_transfert_jamais_acquis() -> None:
    assert not regle_satisfaite(_trois_revues_reussies(), transferts_reussis=0, regles=REGLES)


def test_les_seuils_viennent_des_constantes() -> None:
    carte = _trois_revues_reussies()
    assert not regle_satisfaite(carte, 1, replace(REGLES, retention=0.95))
    assert not regle_satisfaite(carte, 1, replace(REGLES, horizon_jours=365))
    assert regle_satisfaite(carte, 0, replace(REGLES, transferts_requis=0))
