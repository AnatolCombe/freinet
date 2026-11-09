"""Le canal vers l'imprimante, sans rien savoir d'ESC/POS : écrire des octets, en lire un
dans un délai, écarter ce qui traîne. Deux transports derrière la même interface : TCP (port
9100, Ethernet) et USB (pyusb + libusb, la TM-m30II-H branchée au Mac). `imprimante.py` garde
toute la logique d'état avant / confirmation après, identique pour les deux (#80).

Constaté sur la TM-m30II-H (2026-09-30) : après une demande, la première lecture USB rend
souvent un paquet vide ; la réponse vient à la suivante. On relit donc jusqu'au délai.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol

import usb.core  # type: ignore[import-untyped]
import usb.util  # type: ignore[import-untyped]

MORCEAU = 4096  # octets par écriture USB
PAQUET = 64  # taille d'un paquet USB entrant (bulk, pleine vitesse)
ATTENTE_MS = 200  # une lecture USB rend la main au plus tard après ce délai
ECRITURE_MS = 60_000  # l'imprimante lit moins vite qu'on écrit : une minute par morceau
REPOS = 0.01  # secondes entre deux paquets vides, pour ne pas tourner à vide


class ImprimanteIntrouvable(OSError):
    """Rien au bout du câble : pas d'imprimante USB, ou libusb absent."""


class Liaison(Protocol):
    def ecrire(self, donnees: bytes) -> None: ...

    def octet(self, delai: float) -> int:
        """Le prochain octet reçu ; `TimeoutError` si rien n'arrive dans `delai` secondes."""
        ...

    def vider(self, delai: float) -> None:
        """Écarte tout ce qui arrive jusqu'à `delai` secondes de silence."""
        ...


class LiaisonTCP:
    def __init__(self, connexion: socket.socket, delai: float) -> None:
        self.connexion = connexion
        self.delai = delai

    def ecrire(self, donnees: bytes) -> None:
        self.connexion.settimeout(self.delai)
        self.connexion.sendall(donnees)

    def octet(self, delai: float) -> int:
        self.connexion.settimeout(delai)
        recu = self.connexion.recv(1)
        if not recu:
            raise ConnectionError("l'imprimante a fermé la connexion")
        return recu[0]

    def vider(self, delai: float) -> None:
        self.connexion.settimeout(delai)
        try:
            while self.connexion.recv(64):
                pass
        except TimeoutError:
            pass


@contextmanager
def par_tcp(hote: str, port: int, delai: float) -> Iterator[LiaisonTCP]:
    with socket.create_connection((hote, port), timeout=delai) as connexion:
        yield LiaisonTCP(connexion, delai)


class Sortie(Protocol):
    def write(self, data: bytes, timeout: int) -> int: ...


class Entree(Protocol):
    def read(self, size: int, timeout: int) -> Sequence[int]: ...


class LiaisonUSB:
    def __init__(self, sortie: Sortie, entree: Entree) -> None:
        self.sortie = sortie
        self.entree = entree
        self.tampon = bytearray()

    def ecrire(self, donnees: bytes) -> None:
        for debut in range(0, len(donnees), MORCEAU):
            morceau = donnees[debut : debut + MORCEAU]
            if self.sortie.write(morceau, ECRITURE_MS) != len(morceau):
                raise ConnectionError("écriture USB incomplète")

    def _lire(self, jusqua: float) -> bool:
        """Ajoute au tampon le premier paquet non vide reçu avant `jusqua` (horloge
        monotone) ; False si le délai passe sans rien."""
        while (reste := jusqua - time.monotonic()) > 0:
            try:
                paquet = self.entree.read(PAQUET, max(1, min(ATTENTE_MS, int(reste * 1000))))
            except usb.core.USBTimeoutError:
                continue
            if paquet:
                self.tampon += bytes(paquet)
                return True
            time.sleep(REPOS)
        return False

    def octet(self, delai: float) -> int:
        if not self.tampon and not self._lire(time.monotonic() + delai):
            raise TimeoutError("l'imprimante n'a pas répondu")
        premier = self.tampon[0]
        del self.tampon[0]
        return premier

    def vider(self, delai: float) -> None:
        self.tampon.clear()
        while self._lire(time.monotonic() + delai):
            self.tampon.clear()


@contextmanager
def par_usb(vendeur: int, produit: int) -> Iterator[LiaisonUSB]:  # pragma: no cover — matériel
    try:
        appareil = usb.core.find(idVendor=vendeur, idProduct=produit)
    except usb.core.NoBackendError as absent:
        raise ImprimanteIntrouvable("libusb introuvable : brew install libusb") from absent
    if appareil is None:
        raise ImprimanteIntrouvable("imprimante introuvable en USB : branchée, allumée ?")
    try:
        appareil.set_configuration()
        interface = appareil.get_active_configuration()[(0, 0)]

        def point(sens: int) -> Any:
            return usb.util.find_descriptor(
                interface,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == sens,
            )

        sortie, entree = point(usb.util.ENDPOINT_OUT), point(usb.util.ENDPOINT_IN)
        if sortie is None or entree is None:
            raise ImprimanteIntrouvable("interface USB sans point d'accès d'entrée et de sortie")
        yield LiaisonUSB(sortie, entree)
    finally:
        usb.util.dispose_resources(appareil)
