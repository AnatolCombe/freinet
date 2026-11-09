import pytest

from freinet.modele import EtatConcept, Revue
from tests.socle.fabrique import T0, revue


def test_revue_invalide_refusee() -> None:
    with pytest.raises(ValueError, match="nature"):
        revue("x", nature="inconnue")
    with pytest.raises(ValueError, match="note"):
        revue("x", note=5)
    with pytest.raises(ValueError, match="fuseau"):
        Revue("x", "b1", "c1", "q", "rappel", 3, T0.replace(tzinfo=None), T0, "qr")


def test_etat_derive_de_la_date_d_acquisition() -> None:
    assert EtatConcept("b1", "c1", "{}", 1, None).etat == "en_cours"
    assert EtatConcept("b1", "c1", "{}", 3, T0).etat == "acquis"
