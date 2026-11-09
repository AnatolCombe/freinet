"""`quotidien/03_rendu` : envoi du ticket à la TM-m30II-H en ESC/POS brut (#80).

Pas de pilote ni de `python-escpos` : initialiser, image raster `GS v 0` par bandes, avancer
jusqu'au couteau et couper. « Imprimé » ne veut pas dire « octets acceptés » : avant l'envoi,
l'état en temps réel (`DLE EOT`) refuse une imprimante hors ligne ou sans papier ; après, la
demande `GS r 1`, traitée seulement une fois les données imprimées, confirme la sortie du
ticket. Le transport (port 9100 ou USB) est dans `liaison.py` ; `_config/imprimante.md` dit
lequel (`Connexion`) et, en Ethernet, l'adresse.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from freinet.liaison import Liaison, par_tcp, par_usb

FICHIER_IMPRIMANTE = Path(__file__).resolve().parent.parent / "_config" / "imprimante.md"
PORT = 9100
VENDEUR_EPSON, PRODUIT_TM_M30II_H = 0x04B8, 0x0E2A  # relevés par system_profiler (2026-09-30)
BANDE = 256  # lignes de points par commande raster
INITIALISER = b"\x1b@"
AVANCER_ET_COUPER = b"\x1dVB\x00"  # GS V 66 0 : avance jusqu'au couteau, coupe partielle
DLE_EOT = b"\x10\x04"  # état en temps réel : 1 imprimante, 2 cause hors ligne, 4 papier
CONFIRMER = b"\x1dr\x01"  # GS r 1 : état du papier, répondu après les données qui précèdent
SANS_ASB = b"\x1da\x00"  # GS a 0 : pas d'état automatique non sollicité pendant l'échange
PURGE = 0.3  # secondes pour vider un éventuel état automatique déjà envoyé
HORS_LIGNE = 0x08
CAPOT_OUVERT, FIN_PAPIER_ARRET, ERREUR = 0x04, 0x20, 0x40
PAPIER_ABSENT = 0x60  # DLE EOT 4, bits 5-6
PAPIER_EPUISE = 0x0C  # GS r 1, bits 2-3
PAPIER_BIENTOT_FINI = 0x0C  # DLE EOT 4, bits 2-3
_CELLULE = re.compile(r"^\|\s*(IP|Port|Connexion)\s*\|\s*([^|]*?)\s*\|\s*$", re.MULTILINE)
_HOTE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


class ImprimanteIndisponible(OSError):
    """L'imprimante a répondu, mais le ticket ne peut pas sortir (hors ligne, sans papier)."""


@dataclass(frozen=True)
class Imprimante:
    """En Ethernet : ESC/POS brut sur `hote:port`."""

    hote: str
    port: int = PORT


@dataclass(frozen=True)
class ImprimanteUSB:
    """Branchée au Mac en USB, reconnue par ses identifiants."""

    vendeur: int = VENDEUR_EPSON
    produit: int = PRODUIT_TM_M30II_H


Cible = Imprimante | ImprimanteUSB
Ouvrir = Callable[[Cible, float], AbstractContextManager[Liaison]]


def ouvrir_liaison(cible: Cible, delai: float) -> AbstractContextManager[Liaison]:
    if isinstance(cible, ImprimanteUSB):
        return par_usb(cible.vendeur, cible.produit)
    return par_tcp(cible.hote, cible.port, delai)


def imprimante(adresse: str) -> Cible:
    """`usb`, `hote` ou `hote:port` ; refuse ce qui n'est ni une IP ni un nom d'hôte."""
    if adresse.strip().lower() == "usb":
        return ImprimanteUSB()
    hote, _, port = adresse.strip().partition(":")
    try:
        ipaddress.ip_address(hote)
    except ValueError:
        if not _HOTE.match(hote) or hote.replace(".", "").isdigit():
            raise ValueError(f"adresse d'imprimante invalide : {adresse!r}") from None
    if port and not (port.isdigit() and 0 < int(port) < 65536):
        raise ValueError(f"port d'imprimante invalide : {adresse!r}")
    return Imprimante(hote, int(port) if port else PORT)


def lire_imprimante(chemin: Path | None = None) -> Cible:
    chemin = chemin or FICHIER_IMPRIMANTE
    cellules = dict(_CELLULE.findall(chemin.read_text(encoding="utf-8")))
    connexion = cellules.get("Connexion", "ethernet").lower()
    if connexion == "usb":
        return ImprimanteUSB()
    if connexion != "ethernet":
        raise ValueError(f"connexion inconnue {connexion!r} dans {chemin} (usb ou ethernet)")
    ip = cellules.get("IP", "")
    if not ip or ip.startswith("à renseigner"):
        raise ValueError(f"IP de l'imprimante à renseigner dans {chemin}")
    port = cellules.get("Port", "")
    cible = imprimante(f"{ip}:{port}" if port else ip)
    if isinstance(cible, ImprimanteUSB):
        raise ValueError(f"IP invalide dans {chemin} : {ip!r}")
    return cible


def escpos(image: Image.Image) -> bytes:
    """Le ticket 1 bit en commandes ESC/POS (un bit à 1 = un point noir)."""
    noir_et_blanc = image.convert("1", dither=Image.Dither.NONE)
    largeur = (noir_et_blanc.width + 7) // 8
    if noir_et_blanc.width % 8:
        plus = Image.new("1", (largeur * 8, noir_et_blanc.height), 1)
        plus.paste(noir_et_blanc, (0, 0))
        noir_et_blanc = plus
    donnees = bytearray(INITIALISER)
    for haut in range(0, noir_et_blanc.height, BANDE):
        bande = noir_et_blanc.crop((0, haut, largeur * 8, min(haut + BANDE, noir_et_blanc.height)))
        points = bytes(octet ^ 0xFF for octet in bande.tobytes())  # PIL : 1 = blanc
        donnees += b"\x1dv0\x00" + largeur.to_bytes(2, "little")
        donnees += bande.height.to_bytes(2, "little") + points
    return bytes(donnees + AVANCER_ET_COUPER)


def _etat(liaison: Liaison, n: int, delai: float) -> int:
    liaison.ecrire(DLE_EOT + bytes([n]))
    octet = liaison.octet(delai)
    if octet & 0x93 != 0x12:  # bits fixes d'une réponse DLE EOT : 1 et 4 à 1, 0 et 7 à 0
        raise ImprimanteIndisponible(f"réponse d'état inattendue : {octet:#04x}")
    return octet


def _prete(liaison: Liaison, delai: float) -> None:
    liaison.ecrire(SANS_ASB)
    liaison.vider(PURGE)  # écarte les octets d'état automatique (ASB) arrivés avant nos demandes
    if _etat(liaison, 1, delai) & HORS_LIGNE:
        cause = _etat(liaison, 2, delai)
        if cause & CAPOT_OUVERT:
            raison = "capot ouvert"
        elif cause & FIN_PAPIER_ARRET:
            raison = "plus de papier"
        elif cause & ERREUR:
            raison = "en erreur"
        else:
            raison = "hors ligne"
        raise ImprimanteIndisponible(f"imprimante {raison}")
    if _etat(liaison, 4, delai) & PAPIER_ABSENT:
        raise ImprimanteIndisponible("imprimante : plus de papier")


def etat_papier(cible: Cible, delai: float = 5.0, ouvrir: Ouvrir = ouvrir_liaison) -> str:
    """`ok`, `bientôt fini` ou la raison qui empêche d'imprimer (heartbeat, #44). Lève
    `OSError` si l'imprimante ne répond pas."""
    with ouvrir(cible, delai) as liaison:
        try:
            _prete(liaison, delai)
        except ImprimanteIndisponible as raison:
            return str(raison)
        return "bientôt fini" if _etat(liaison, 4, delai) & PAPIER_BIENTOT_FINI else "ok"


def envoyer(
    donnees: bytes,
    cible: Cible,
    delai: float = 10.0,
    fin: float = 90.0,
    ouvrir: Ouvrir = ouvrir_liaison,
) -> None:
    """Envoie le ticket et attend que l'imprimante confirme l'avoir traité. Lève `OSError`
    (dont `ImprimanteIndisponible` et `TimeoutError`) si le ticket n'est pas sorti."""
    with ouvrir(cible, delai) as liaison:
        _prete(liaison, delai)
        liaison.ecrire(donnees + CONFIRMER)
        papier = liaison.octet(fin)
        while papier & 0x93 == 0x12:
            # Une séquence DLE EOT fortuite dans l'image : sa réponse (bit 4 à 1) précède
            # celle de GS r 1 (bit 4 à 0), on l'écarte.
            papier = liaison.octet(fin)
        if papier & 0x90:
            raise ImprimanteIndisponible(f"confirmation inattendue : {papier:#04x}")
        if papier & PAPIER_EPUISE:
            raise ImprimanteIndisponible("papier épuisé pendant l'impression")
