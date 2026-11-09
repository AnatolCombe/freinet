"""Une TM-m30II-H factice sur 127.0.0.1 : elle répond à `DLE EOT` et confirme le ticket
(`GS r 1`) comme la vraie, et garde les données reçues, connexion par connexion."""

import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from freinet.imprimante import CONFIRMER, DLE_EOT, SANS_ASB


@dataclass
class Etat:
    """Octets rendus aux demandes d'état ; `muette` : ne confirme jamais le ticket."""

    imprimante: int = 0x12  # DLE EOT 1 : en ligne
    cause: int = 0x12  # DLE EOT 2 : aucune cause
    papier: int = 0x12  # DLE EOT 4 : papier présent
    confirmation: int = 0x00  # GS r 1 : papier présent
    muette: bool = False
    asb: bool = False  # envoie un état automatique (4 octets) dès la connexion
    parasite: bool = False  # répond aussi à un DLE EOT fortuit juste avant la confirmation


class FausseImprimante:
    def __init__(self, etat: Etat) -> None:
        self.etat = etat
        self.serveur = socket.create_server(("127.0.0.1", 0))
        self.serveur.settimeout(0.2)
        self.port = self.serveur.getsockname()[1]
        self.recus: list[bytes] = []
        self._arret = threading.Event()
        self._fil = threading.Thread(target=self._ecouter, daemon=True)
        self._fil.start()

    def _ecouter(self) -> None:
        while not self._arret.is_set():
            try:
                connexion, _ = self.serveur.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connexion:
                self._servir(connexion)

    def _servir(self, connexion: socket.socket) -> None:
        reponses = {1: self.etat.imprimante, 2: self.etat.cause, 4: self.etat.papier}
        if self.etat.asb:
            connexion.sendall(b"\x14\x00\x00\x0f")
        tampon = b""
        donnees = b""
        while morceau := connexion.recv(65536):
            tampon += morceau
            if not donnees and tampon.startswith(SANS_ASB):
                tampon = tampon.removeprefix(SANS_ASB)
            while not donnees and tampon[:2] == DLE_EOT and len(tampon) >= 3:
                connexion.sendall(bytes([reponses[tampon[2]]]))
                tampon = tampon[3:]
            if tampon[:2] != DLE_EOT[: len(tampon[:2])]:
                donnees += tampon
                tampon = b""
            if donnees.endswith(CONFIRMER):
                self.recus.append(donnees.removesuffix(CONFIRMER))
                if self.etat.parasite:
                    connexion.sendall(b"\x16")
                if not self.etat.muette:
                    connexion.sendall(bytes([self.etat.confirmation]))
                donnees = b""

    def fermer(self) -> None:
        self._arret.set()
        self.serveur.close()
        self._fil.join(timeout=5)


@contextmanager
def fausse_imprimante(etat: Etat | None = None) -> Iterator[FausseImprimante]:
    imprimante = FausseImprimante(etat or Etat())
    try:
        yield imprimante
    finally:
        imprimante.fermer()


def port_ferme() -> int:
    """Un port où rien n'écoute (réservé puis relâché)."""
    with socket.create_server(("127.0.0.1", 0)) as serveur:
        port: int = serveur.getsockname()[1]
    return port
