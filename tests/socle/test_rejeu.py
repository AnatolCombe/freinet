from datetime import timedelta

import pytest

from freinet.constantes import lire_regles
from freinet.rejeu import effectives, rejouer
from tests.socle.fabrique import T0, revue

REGLES = lire_regles()

# Trois « Bien » aux échéances FSRS (J0, J2, J13), dont un transfert réussi.
ACQUISITION = [
    revue("r1", nature="rappel", note=3, jour=0),
    revue("r2", nature="application", note=3, jour=2),
    revue("r3", nature="transfert", note=3, jour=13),
]


def test_ordre_total_par_reponse_puis_id() -> None:
    a = revue("b", jour=1)
    b = revue("a", jour=1)
    c = revue("c", jour=0, saisi_jour=5)
    assert [r.revue_id for r in effectives([a, b, c])] == ["c", "a", "b"]


def test_correction_remplace_la_note_sans_bouger_l_heure() -> None:
    origine = revue("r1", note=1, jour=0)
    correction = revue("r2", note=3, jour=0, saisi_jour=0.1, corrige_id="r1")
    [effective] = effectives([origine, correction])
    assert effective.revue_id == "r1"
    assert effective.note == 3
    assert effective.repondu_le == T0


def test_derniere_correction_saisie_l_emporte() -> None:
    origine = revue("r1", note=1)
    tardive = revue("r3", note=4, saisi_jour=2, corrige_id="r1")
    precoce = revue("r2", note=2, saisi_jour=1, corrige_id="r1")
    [effective] = effectives([origine, tardive, precoce])
    assert effective.note == 4


def test_correction_d_une_correction_remonte_a_l_origine() -> None:
    origine = revue("r1", note=1)
    premiere = revue("r2", note=2, saisi_jour=1, corrige_id="r1")
    seconde = revue("r3", note=4, saisi_jour=2, corrige_id="r2")
    [effective] = effectives([seconde, origine, premiere])
    assert (effective.revue_id, effective.note) == ("r1", 4)


def test_cycle_de_corrections_refuse() -> None:
    a = revue("a", corrige_id="b")
    b = revue("b", corrige_id="a")
    with pytest.raises(ValueError, match="cycle"):
        effectives([a, b])


def test_transfert_corrige_en_reussite_compte_pour_acquis() -> None:
    rate = revue("r3", nature="transfert", note=1, jour=13)
    correction = revue("c3", nature="rappel", note=3, jour=13, saisi_jour=14, corrige_id="r3")
    [etat] = rejouer([*ACQUISITION[:2], rate, correction], REGLES)
    assert etat.acquis_le == T0 + timedelta(days=13)


def test_pre_test_ne_pese_pas_sur_fsrs() -> None:
    avec = rejouer([revue("p", nature="pre_test", note=1, jour=0), *ACQUISITION], REGLES)
    sans = rejouer(ACQUISITION, REGLES)
    assert avec == sans


def test_acquisition_datee_a_la_revue_qui_satisfait_la_regle() -> None:
    [etat] = rejouer(ACQUISITION, REGLES)
    assert etat.etat == "acquis"
    assert etat.acquis_le == T0 + timedelta(days=13)
    assert etat.nb_revues == 3


def test_acquis_ne_recule_pas() -> None:
    oublis = [revue(f"o{i}", note=1, jour=60 + i) for i in range(5)]
    [etat] = rejouer([*ACQUISITION, *oublis], REGLES)
    assert etat.etat == "acquis"
    assert etat.acquis_le == T0 + timedelta(days=13)


def test_concepts_et_eleves_separes() -> None:
    revues = [
        revue("r1", brainiac_id="b2", concept_id="c1"),
        revue("r2", brainiac_id="b1", concept_id="c2"),
        revue("r3", brainiac_id="b1", concept_id="c1"),
    ]
    cles = [(e.brainiac_id, e.concept_id) for e in rejouer(revues, REGLES)]
    assert cles == [("b1", "c1"), ("b1", "c2"), ("b2", "c1")]
