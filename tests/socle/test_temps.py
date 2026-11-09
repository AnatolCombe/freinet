from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from freinet.temps import date_logique, depuis_iso, maintenant, vers_iso


def test_vers_iso_normalise_en_utc() -> None:
    paris = datetime(2026, 9, 30, 8, 0, tzinfo=ZoneInfo("Europe/Paris"))
    assert vers_iso(paris) == "2026-09-30T06:00:00+00:00"


def test_aller_retour_iso() -> None:
    instant = datetime(2026, 9, 30, 6, 0, 12, 345678, tzinfo=UTC)
    assert depuis_iso(vers_iso(instant)) == instant


def test_depuis_iso_accepte_z_et_decalage() -> None:
    attendu = datetime(2026, 9, 30, 6, 0, tzinfo=UTC)
    assert depuis_iso("2026-09-30T06:00:00Z") == attendu
    assert depuis_iso("2026-09-30T08:00:00+02:00") == attendu


def test_instant_sans_fuseau_refuse() -> None:
    with pytest.raises(ValueError, match="sans fuseau"):
        vers_iso(datetime(2026, 9, 30, 6, 0))
    with pytest.raises(ValueError, match="sans fuseau"):
        depuis_iso("2026-09-30T06:00:00")
    with pytest.raises(ValueError, match="sans fuseau"):
        date_logique(datetime(2026, 9, 30, 6, 0), "Europe/Paris")


def test_maintenant_est_en_utc() -> None:
    assert maintenant().utcoffset() is not None
    assert maintenant().tzinfo == UTC


def test_date_logique_ami_a_montreal() -> None:
    # 3 h UTC le 30 = 23 h la veille à Montréal : son plan est celui du 29.
    instant = datetime(2026, 9, 30, 3, 0, tzinfo=UTC)
    assert date_logique(instant, "America/Montreal") == date(2026, 9, 29)
    assert date_logique(instant, "Europe/Paris") == date(2026, 9, 30)


@pytest.mark.parametrize(
    ("instant", "attendu"),
    [
        # passage à l'heure d'été (29 mars 2026, 2 h → 3 h à Paris)
        (datetime(2026, 3, 28, 23, 30, tzinfo=UTC), date(2026, 3, 29)),
        (datetime(2026, 3, 29, 4, 0, tzinfo=UTC), date(2026, 3, 29)),
        (datetime(2026, 3, 29, 22, 30, tzinfo=UTC), date(2026, 3, 30)),
        # retour à l'heure d'hiver (25 octobre 2026, 3 h → 2 h à Paris)
        (datetime(2026, 10, 24, 22, 30, tzinfo=UTC), date(2026, 10, 25)),
        (datetime(2026, 10, 25, 4, 0, tzinfo=UTC), date(2026, 10, 25)),
    ],
)
def test_date_logique_nuits_de_changement_d_heure(instant: datetime, attendu: date) -> None:
    assert date_logique(instant, "Europe/Paris") == attendu
