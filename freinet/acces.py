"""Accès à la page du QR : un jeton aléatoire de 128 bits et un code court de secours (#34).

Tous deux sont tirés au hasard (`secrets`), jamais dérivés de la graine de sélection, et
stockés hachés dans la base (A1) par HMAC-SHA256 avec une clé locale (`data/.cle-acces`, 0600)
qui ne voyage pas avec les sauvegardes : une copie de la base ne redonne pas les codes courts
(2^40 possibilités se parcourent vite sans clé). Le clair ne vit que sur le ticket et dans un
fichier privé à côté de lui (`acces-AAAA-MM-JJ.txt`, 0600) : un nouveau rendu du même jour
garde le même QR, et le ticket déjà imprimé reste valable.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
import re
import secrets
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from freinet.base import Base

FICHIER_RETOUR = Path(__file__).resolve().parent.parent / "_config" / "retour.md"
_CELLULE = re.compile(
    r"^\|\s*(Écoute|Port|Adresse du QR|QR vers ADVIZA)\s*\|\s*([^|]*?)\s*\|\s*$", re.MULTILINE
)
_ADRESSE = re.compile(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?")
CHEMIN_ADVIZA = "/profil/freinet/aujourdhui"  # la page « Aujourd'hui » d'ADVIZA (PROF-A)
ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans I, O, 0, 1 : rien à confondre
LONGUEUR_CODE = 8  # 32^8 = 2^40 ; la page limite les essais
TAILLE_CLE = 32


@dataclass(frozen=True)
class ConfigRetour:
    ecoute: str
    port: int
    adresse: str  # base des liens du QR, sans « / » final
    adviza: str | None = None  # base d'ADVIZA : le QR ouvre sa page « Aujourd'hui » (PROF-A)

    def lien_du_qr(self, jeton: str) -> str:
        """Ce qu'ouvre le QR : la page « Aujourd'hui » d'ADVIZA si elle est réglée, sinon
        l'espace du ticket sur la page du QR. Le code court reste celui de FREINET (`/c`)."""
        if self.adviza:
            return f"{self.adviza}{CHEMIN_ADVIZA}"
        return f"{self.adresse}/r/{jeton}"

    @property
    def page_code(self) -> str:
        """Où taper le code court, sans le schéma (plus court à recopier)."""
        return f"{self.adresse.split('://', 1)[-1]}/c"


def nom_local() -> str:
    """Le nom Bonjour du Mac (`<nom>.local`), que le téléphone résout sur le Wi-Fi."""
    try:
        sortie = subprocess.run(
            # Chemin complet : le PATH de launchd n'a pas /usr/sbin.
            ["/usr/sbin/scutil", "--get", "LocalHostName"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        nom = sortie.stdout.strip() if sortie.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        nom = ""
    return f"{nom or socket.gethostname().split('.')[0]}.local"


def lire_config_retour(chemin: Path | None = None) -> ConfigRetour:
    chemin = chemin or FICHIER_RETOUR
    cellules = dict(_CELLULE.findall(chemin.read_text(encoding="utf-8")))
    port = cellules.get("Port", "8765")
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError(f"port invalide dans {chemin} : {port!r}")
    adresse = cellules.get("Adresse du QR", "auto")
    if adresse == "auto":
        adresse = f"http://{nom_local()}:{port}"
    if not _ADRESSE.fullmatch(adresse):
        raise ValueError(f"adresse du QR invalide dans {chemin} : {adresse!r}")
    adviza = cellules.get("QR vers ADVIZA", "aucune")
    if adviza != "aucune" and not _ADRESSE.fullmatch(adviza):
        raise ValueError(f"QR vers ADVIZA invalide dans {chemin} : {adviza!r}")
    ecoute = cellules.get("Écoute", "0.0.0.0")
    return ConfigRetour(ecoute, int(port), adresse, None if adviza == "aucune" else adviza)


@dataclass(frozen=True)
class Acces:
    jeton: str
    code: str


def cle_acces(racine: Path) -> bytes:
    """La clé de hachage des accès, créée au premier usage (0600, jamais écrasée). Publiée
    par lien dur d'un fichier complet : un lecteur concurrent ne voit jamais une clé vide."""
    chemin = racine / "data" / ".cle-acces"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if not chemin.exists():
        descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, suffix=".tmp")  # 0600
        try:
            with os.fdopen(descripteur, "w", encoding="ascii") as fichier:
                fichier.write(secrets.token_bytes(TAILLE_CLE).hex())
            with contextlib.suppress(FileExistsError):  # un autre processus a gagné
                os.link(temporaire, chemin)
        finally:
            Path(temporaire).unlink(missing_ok=True)
    try:
        cle = bytes.fromhex(chemin.read_text(encoding="ascii").strip())
    except (ValueError, UnicodeDecodeError):
        cle = b""
    if len(cle) != TAILLE_CLE:
        raise ValueError(f"clé d'accès abîmée : {chemin} (la supprimer, puis --nouvel-acces)")
    return cle


def hacher(cle: bytes, secret: str) -> str:
    return hmac.new(cle, secret.encode("ascii"), hashlib.sha256).hexdigest()


def nouvel_acces() -> Acces:
    code = "".join(secrets.choice(ALPHABET_CODE) for _ in range(LONGUEUR_CODE))
    return Acces(secrets.token_urlsafe(16), code)


def code_lisible(code: str) -> str:
    """`ABCD-EFGH` : deux groupes, plus faciles à recopier."""
    return f"{code[:4]}-{code[4:]}"


def normaliser_code(saisie: str) -> str:
    """Ce qu'on tape sur la page : casse, espaces, tirets et tout ce qui n'est pas de
    l'alphabet du code ignorés."""
    return "".join(c for c in saisie.upper() if c in ALPHABET_CODE)


def _lire(chemin: Path) -> Acces | None:
    try:
        lignes = chemin.read_text(encoding="ascii").split()
    except (OSError, UnicodeDecodeError):
        return None
    return Acces(lignes[0], lignes[1]) if len(lignes) == 2 else None


def _ecrire(chemin: Path, acces: Acces) -> None:
    descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, suffix=".tmp")  # 0600
    try:
        with os.fdopen(descripteur, "w", encoding="ascii") as fichier:
            fichier.write(f"{acces.jeton}\n{acces.code}\n")
        os.replace(temporaire, chemin)
    finally:
        Path(temporaire).unlink(missing_ok=True)


def acces_du_jour(
    base: Base, brainiac_id: str, jour: date, dossier: Path, cle: bytes, renouveler: bool = False
) -> Acces:
    """L'accès du plan de ce jour : celui déjà attribué si son clair est encore là et
    correspond à la base, sinon un nouveau (qui révoque l'ancien). `renouveler` force."""
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"acces-{jour.isoformat()}.txt"
    connu = None if renouveler else _lire(chemin)
    if connu is not None and base.acces_du_plan(brainiac_id, jour) == (
        hacher(cle, connu.jeton),
        hacher(cle, connu.code),
    ):
        return connu
    acces = nouvel_acces()
    base.attribuer_acces(brainiac_id, jour, hacher(cle, acces.jeton), hacher(cle, acces.code))
    _ecrire(chemin, acces)
    return acces
