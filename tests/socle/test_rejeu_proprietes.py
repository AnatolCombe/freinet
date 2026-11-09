"""Test de propriété du rejeu (#17, inv. 4) : le journal est la seule vérité."""

from dataclasses import replace
from datetime import datetime, timedelta
from random import Random

from hypothesis import given, settings
from hypothesis import strategies as st

from freinet.base import Base
from freinet.constantes import lire_regles
from freinet.etat import etat_coherent, recalculer
from freinet.modele import NATURES, Revue
from freinet.rejeu import effectives, rejouer
from tests.socle.fabrique import revue

REGLES = lire_regles()


@st.composite
def journaux(draw: st.DrawFn) -> list[Revue]:
    n = draw(st.integers(min_value=0, max_value=25))
    revues = []
    for i in range(n):
        jour = draw(st.integers(min_value=0, max_value=120))  # doublons de jour : départage par id
        revues.append(
            revue(
                f"r{i:03d}",
                concept_id=draw(st.sampled_from(["c1", "c2", "c3"])),
                nature=draw(st.sampled_from(NATURES)),
                note=draw(st.integers(min_value=1, max_value=4)),
                jour=jour,
                saisi_jour=jour + draw(st.integers(min_value=0, max_value=3)),
            )
        )
    return revues


@st.composite
def journaux_corriges(draw: st.DrawFn) -> list[Revue]:
    """Journal + corrections (y compris corrections de corrections), jamais de cycle."""
    revues = draw(journaux())
    if not revues:
        return revues
    for i in range(draw(st.integers(min_value=0, max_value=6))):
        cible = draw(st.sampled_from(revues))
        decalage = draw(st.integers(min_value=0, max_value=4))
        revues.append(
            replace(
                cible,
                revue_id=f"k{i:03d}",
                note=draw(st.integers(min_value=1, max_value=4)),
                saisi_le=cible.saisi_le + timedelta(days=decalage),
                corrige_id=cible.revue_id,
            )
        )
    return revues


@given(journaux_corriges(), st.randoms(use_true_random=False))
def test_rejeu_independant_de_l_ordre_de_lecture(revues: list[Revue], hasard: Random) -> None:
    melange = list(revues)
    hasard.shuffle(melange)
    assert rejouer(melange, REGLES) == rejouer(revues, REGLES)


@given(journaux())
def test_acquis_monotone_sur_chaque_prefixe(revues: list[Revue]) -> None:
    ordonnees = effectives(revues)
    precedent: dict[str, datetime | None] = {}
    for k in range(1, len(ordonnees) + 1):
        courant = {e.concept_id: e.acquis_le for e in rejouer(ordonnees[:k], REGLES)}
        for concept, acquis_le in precedent.items():
            if acquis_le is not None:
                assert courant[concept] == acquis_le
        precedent = dict(courant)


@settings(max_examples=50)
@given(journaux_corriges())
def test_rejeu_identique(revues: list[Revue]) -> None:
    with Base(":memory:") as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        for r in revues:
            base.ajouter_revue(replace(r, brainiac_id=b))
        premier = recalculer(base, b, REGLES)
        assert etat_coherent(base, b, REGLES)
        assert recalculer(base, b, REGLES) == premier


def test_caches_perimes_detectes_puis_reconstruits() -> None:
    with Base(":memory:") as base:
        b = base.ajouter_brainiac("marius", "Europe/Paris")
        base.ajouter_revue(revue("r1", brainiac_id=b))
        recalculer(base, b, REGLES)
        assert etat_coherent(base, b, REGLES)
        base.ajouter_revue(revue("r2", brainiac_id=b, jour=2))
        assert not etat_coherent(base, b, REGLES)
        recalculer(base, b, REGLES)
        assert etat_coherent(base, b, REGLES)
