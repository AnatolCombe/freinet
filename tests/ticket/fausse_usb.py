"""Des points d'accès USB factices branchés sur la fausse imprimante TCP : le même
protocole, mais le comportement d'un bus USB — un paquet vide avant chaque réponse, et
`USBTimeoutError` quand rien n'arrive dans le délai (en millisecondes)."""

import socket
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager

import usb.core  # type: ignore[import-untyped]

from freinet.imprimante import Cible, Ouvrir
from freinet.liaison import Liaison, LiaisonUSB


class PointsUSB:
    def __init__(self, port: int) -> None:
        self.connexion = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.vide = False

    def write(self, data: bytes, timeout: int) -> int:
        self.connexion.sendall(data)
        return len(data)

    def read(self, size: int, timeout: int) -> list[int]:
        self.vide = not self.vide
        if self.vide:
            return []  # paquet de longueur nulle, comme la vraie TM-m30II-H
        self.connexion.settimeout(timeout / 1000)
        try:
            recu = self.connexion.recv(size)
        except TimeoutError:
            raise usb.core.USBTimeoutError("Operation timed out") from None
        return list(recu)


@contextmanager
def _pont(port: int) -> Iterator[Liaison]:
    points = PointsUSB(port)
    try:
        yield LiaisonUSB(points, points)
    finally:
        points.connexion.close()


def ouvrir_pont(port: int) -> Ouvrir:
    """Remplace `ouvrir_liaison` : toute cible passe par le pont vers `port`."""

    def ouvrir(cible: Cible, delai: float) -> AbstractContextManager[Liaison]:
        return _pont(port)

    return ouvrir
