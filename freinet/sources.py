"""Registre des sources de confiance (#47) : `_config/sources/<domaine>.md`.

Une source est admise si c'est une URL http(s) sous un domaine du registre (celui du concept,
ou « culture », d'où viennent les anecdotes), ou un ouvrage publié cité « Auteur, Titre (année) ».
Un ouvrage passe le contrôle mécanique mais reste vérifié à la gate humaine de `05_verification`.

Le contenu vient d'agents qui lisent des pages web hostiles (#45) : tout ce qui ressemble à un
lien (un schéma, `://`, du balisage) est traité comme une URL, donc refusé hors registre.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from freinet.frontmatter import ErreurContenu

DOSSIER_REGISTRE = Path(__file__).resolve().parent.parent / "_config" / "sources"
DOMAINE_COMMUN = "culture"

_ENTREE = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[a-z0-9_~-][a-z0-9._~-]*)*")
_HOTE = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+")
# Caractères admis dans une URL : ni `\` (lu comme `/` par un navigateur), ni espace, ni
# parenthèses, crochets, chevrons, accolades, guillemets ou accent grave (balisage).
_URL_PERMISE = re.compile(r"[A-Za-z0-9\-._~:/?#@!$&*+,;=%]+")
_SCHEMA = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
_OUVRAGE = re.compile(r"[^\W\d_][^\n]{0,80}?, [^\n]{1,200} \((?:1[0-9]{3}|20[0-9]{2})\)")
_BALISAGE = re.compile(r"[<>\[\]{}`]")


@dataclass(frozen=True)
class Registre:
    par_domaine: dict[str, tuple[str, ...]]

    def entrees(self, domaine: str) -> tuple[str, ...]:
        return self.par_domaine.get(domaine, ()) + self.par_domaine.get(DOMAINE_COMMUN, ())


def lire_registre(dossier: Path = DOSSIER_REGISTRE) -> Registre:
    """Chaque ligne du tableau (hors en-tête et séparateur) doit être un domaine lisible."""
    par_domaine: dict[str, tuple[str, ...]] = {}
    for fichier in sorted(dossier.glob("*.md")):
        if fichier.name == "CONTEXT.md":
            continue
        entrees = []
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if not ligne.startswith("|") or re.fullmatch(r"\|[\s:|-]+", ligne):
                continue
            cellule = ligne.strip("|").split("|")[0].strip().lower()
            if cellule == "domaine":
                continue
            cellule = cellule.removeprefix("www.").rstrip("/")
            if not _ENTREE.fullmatch(cellule):
                raise ErreurContenu(fichier, f"ligne de registre illisible : {ligne!r}")
            entrees.append(cellule)
        par_domaine[fichier.stem] = tuple(entrees)
    return Registre(par_domaine)


def _url_admise(url: str, entrees: tuple[str, ...]) -> bool:
    if not _URL_PERMISE.fullmatch(url) or url.count("://") != 1:
        return False
    morceaux = urlsplit(url)
    try:
        port = morceaux.port
    except ValueError:
        return False
    if (
        morceaux.scheme.lower() not in ("http", "https")
        or not morceaux.hostname
        or morceaux.username is not None
        or port not in (None, 80, 443)
    ):
        return False
    chemin_brut = unquote(morceaux.path)
    if ".." in chemin_brut.split("/"):
        return False
    hote = morceaux.hostname.removeprefix("www.")
    if not _HOTE.fullmatch(hote):
        return False
    chemin = posixpath.normpath("/" + chemin_brut.lstrip("/"))
    for entree in entrees:
        domaine, _, prefixe = entree.partition("/")
        prefixe = "/" + prefixe
        dans_le_chemin = prefixe == "/" or chemin == prefixe or chemin.startswith(prefixe + "/")
        if (hote == domaine or hote.endswith("." + domaine)) and dans_le_chemin:
            return True
    return False


def _ouvrage_admis(reference: str) -> bool:
    """Forme « Auteur, Titre (année) », en texte brut : rien qu'un afficheur transformerait
    en lien (`/`, `@`, `www.`), ni balisage, ni caractère de contrôle ou d'inversion."""
    if _BALISAGE.search(reference) or any(c in reference for c in "/@"):
        return False
    if "www." in reference.casefold():
        return False
    if any(unicodedata.category(c).startswith("C") for c in reference):
        return False
    return _OUVRAGE.fullmatch(reference) is not None


def refus(reference: str, domaine: str, registre: Registre) -> str | None:
    """None si la source est admise, sinon la raison du refus."""
    if _SCHEMA.match(reference) or "://" in reference:
        if _url_admise(reference, registre.entrees(domaine)):
            return None
        if all(c.isalnum() or c in "()" or _URL_PERMISE.fullmatch(c) for c in reference):
            encodee = quote(reference, safe=":/?#@!$&*+,;=%-._~")
            if encodee != reference and _url_admise(encodee, registre.entrees(domaine)):
                return f"URL à encoder (parenthèses, accents → %xx) : {encodee!r}"
        return f"source hors registre pour « {domaine} » : {reference!r}"
    if _ouvrage_admis(reference):
        return None
    return f"source ni URL du registre ni ouvrage « Auteur, Titre (année) » : {reference!r}"
