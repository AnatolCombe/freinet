from datetime import timedelta
from zoneinfo import ZoneInfo

from freinet.planification import (
    carte_neuve,
    depuis_json,
    retention,
    reviser,
    vers_json,
)
from tests.socle.fabrique import T0


def test_revision_deterministe() -> None:
    a = reviser(carte_neuve(T0), 3, T0)
    b = reviser(carte_neuve(T0), 3, T0)
    assert vers_json(a) == vers_json(b)


def test_json_aller_retour() -> None:
    carte = reviser(carte_neuve(T0), 4, T0)
    assert vers_json(depuis_json(vers_json(carte))) == vers_json(carte)


def test_concept_rate_revient_le_lendemain_reussi_est_repousse() -> None:
    rate = reviser(carte_neuve(T0), 1, T0)
    reussi = reviser(carte_neuve(T0), 3, T0)
    assert rate.due == T0 + timedelta(days=1)
    assert reussi.due > rate.due


def test_retention_decroit_avec_le_temps() -> None:
    carte = reviser(carte_neuve(T0), 3, T0)
    assert retention(carte, T0 + timedelta(days=1)) > retention(carte, T0 + timedelta(days=30))


def test_instant_d_un_autre_fuseau_accepte() -> None:
    paris = T0.astimezone(ZoneInfo("Europe/Paris"))
    a = reviser(carte_neuve(T0), 3, paris)
    b = reviser(carte_neuve(T0), 3, T0)
    assert vers_json(a) == vers_json(b)
    assert retention(a, paris + timedelta(days=5)) == retention(b, T0 + timedelta(days=5))


def test_reviser_ne_modifie_pas_la_carte_d_origine() -> None:
    carte = reviser(carte_neuve(T0), 3, T0)
    avant = vers_json(carte)
    reviser(carte, 1, T0 + timedelta(days=2))
    assert vers_json(carte) == avant
