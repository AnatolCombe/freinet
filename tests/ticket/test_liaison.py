"""`LiaisonUSB` sans matériel : des points d'accès scriptés imitent le bus."""

import time

import pytest
import usb.core  # type: ignore[import-untyped]

from freinet.liaison import MORCEAU, LiaisonUSB


class Sortie:
    def __init__(self, accepte: int | None = None) -> None:
        self.morceaux: list[bytes] = []
        self.accepte = accepte  # octets réellement écrits par appel (None : tout)

    def write(self, data: bytes, timeout: int) -> int:
        self.morceaux.append(bytes(data))
        return len(data) if self.accepte is None else self.accepte


class Entree:
    """Rend les paquets dans l'ordre ; ensuite, attend le délai puis `USBTimeoutError`."""

    def __init__(self, *paquets: list[int]) -> None:
        self.paquets = list(paquets)
        self.lectures = 0

    def read(self, size: int, timeout: int) -> list[int]:
        self.lectures += 1
        if not self.paquets:
            time.sleep(timeout / 1000)
            raise usb.core.USBTimeoutError("Operation timed out")
        return self.paquets.pop(0)


def test_ecrit_par_morceaux() -> None:
    sortie = Sortie()
    LiaisonUSB(sortie, Entree()).ecrire(b"x" * (2 * MORCEAU + 10))
    assert [len(m) for m in sortie.morceaux] == [MORCEAU, MORCEAU, 10]


def test_ecriture_incomplete() -> None:
    with pytest.raises(ConnectionError, match="incomplète"):
        LiaisonUSB(Sortie(accepte=1), Entree()).ecrire(b"ticket")


def test_saute_les_paquets_vides_et_garde_le_reste() -> None:
    entree = Entree([], [], [0x12, 0x16])
    liaison = LiaisonUSB(Sortie(), entree)
    assert liaison.octet(1.0) == 0x12
    assert liaison.octet(1.0) == 0x16  # déjà dans le tampon : pas de nouvelle lecture
    assert entree.lectures == 3


def test_rien_dans_le_delai() -> None:
    debut = time.monotonic()
    with pytest.raises(TimeoutError):
        LiaisonUSB(Sortie(), Entree()).octet(0.3)
    assert 0.25 < time.monotonic() - debut < 1.0


def test_vider_ecarte_l_etat_automatique() -> None:
    entree = Entree([0x14, 0x00, 0x00, 0x0F], [0x10])
    liaison = LiaisonUSB(Sortie(), entree)
    liaison.vider(0.05)
    assert entree.paquets == []
    with pytest.raises(TimeoutError):
        liaison.octet(0.05)
