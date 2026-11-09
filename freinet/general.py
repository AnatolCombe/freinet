"""La partie générale du ticket, côté factory (L3) : `_config/general/` lu et validé.

`general.md` (ville, coordonnées, fuseau, origine et langues de la rotation, seuil de pluie,
profils des élèves) et trois listes figées, relues par Marius : `mots.md`, `ce-jour-la.md`,
`enigmes.md` (frontmatter YAML). Un élève anglophone (`langue: en`) lit `en/mots.md`,
`en/ce-jour-la.md`, `en/enigmes.md` et la rotation `langues_en` (PROF-12). Tout ce qui
s'imprime est dessinable par la police du ticket et sourcé. Une liste invalide est une
erreur de factory : `ErreurContenu`, message précis, et le passage du matin refuse de
démarrer. `python -m freinet.general` fait le bilan.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from freinet.frontmatter import ErreurContenu, lire
from freinet.imprimable import absents
from freinet.langue import LANGUE_PAR_DEFAUT, LANGUES

DOSSIER_GENERAL = Path(__file__).resolve().parent.parent / "_config" / "general"
TYPES_ENIGME = ("logique", "mots", "chiffres")
LONGUEUR_MAX = 96  # sens, question, fait, solution : deux lignes de 48 colonnes au plus (spec)
LONGUEUR_ENONCE = 200  # trois à quatre lignes de 48 colonnes
NIQQUD = range(0x0591, 0x05C8)  # voyelles et cantillation : l'ordre visuel les casserait
JOURS_DE_L_ANNEE = tuple(f"{date(2024, 1, 1) + timedelta(n):%m-%d}" for n in range(366))
_MM_JJ = re.compile(r"\d\d-\d\d")
_ANNEE = re.compile(r"-?[1-9]\d{0,3}")
SYNTAXE_DU_PLAN = ("#", "[", ">")  # titres, marques, citations (`plan.py`)
CHAMPS_MOT = ("id", "langue", "forme", "prononciation", "sens", "question", "source")
CHAMPS_ENIGME = ("id", "type", "enonce", "solution", "source")


@dataclass(frozen=True)
class Profil:
    prenom: str
    mot_de: str | None = None
    langue: str = LANGUE_PAR_DEFAUT  # celle du plan, du ticket et de l'espace (PROF-12)


@dataclass(frozen=True)
class ConfigGeneral:
    ville: str
    latitude: float
    longitude: float
    fuseau: str
    origine: date
    langues: tuple[str, ...]
    seuil_pluie: int
    profils: dict[str, Profil]
    langues_en: tuple[str, ...] = ()  # rotation des mots pour un élève anglophone

    def rotation(self, langue: str) -> tuple[str, ...]:
        """La rotation des mots du jour d'une langue d'élève (même rang d'une langue à
        l'autre : le jour de l'anglais pour un francophone est celui du français pour un
        anglophone)."""
        if langue == LANGUE_PAR_DEFAUT:
            return self.langues
        if langue == "en" and self.langues_en:
            return self.langues_en
        raise ValueError(f"rotation des mots en {langue} absente (« langues_en » dans general.md)")

    def profil(self, nom: str) -> Profil:
        """Un élève absent de la config a son nom pour prénom, sans mot de l'autre."""
        return self.profils.get(nom, Profil(nom.upper()))


@dataclass(frozen=True)
class Mot:
    id: str
    langue: str
    forme: str
    prononciation: str
    sens: str
    question: str
    source: str


@dataclass(frozen=True)
class Fait:
    jour: str  # MM-JJ
    annee: int  # négative avant J.-C.
    texte: str
    source: str


@dataclass(frozen=True)
class Enigme:
    id: str
    type: str
    enonce: str
    solution: str
    source: str


@dataclass(frozen=True)
class Listes:
    mots: tuple[Mot, ...]
    faits: dict[str, Fait]
    enigmes: tuple[Enigme, ...]
    rotation: tuple[str, ...]


def _texte(chemin: Path, entree: dict[str, object], cle: str, rang: int) -> str:
    valeur = entree.get(cle)
    if not isinstance(valeur, str) or not valeur.strip():
        ident = entree.get("id") or entree.get("jour") or f"entrée n° {rang + 1}"
        raise ErreurContenu(chemin, f"{ident} : champ « {cle} » vide ou absent")
    return valeur.strip()


def _entrees(chemin: Path, cle: str) -> list[dict[str, object]]:
    entete, _ = lire(chemin)
    entrees = entete.get(cle)
    if not isinstance(entrees, list):
        raise ErreurContenu(chemin, f"liste « {cle} » attendue dans le frontmatter")
    for rang, entree in enumerate(entrees):
        if not isinstance(entree, dict):
            raise ErreurContenu(chemin, f"liste « {cle} », entrée n° {rang + 1} : table attendue")
    return entrees


def _imprimables(chemin: Path, ident: str, *textes: str) -> None:
    """Dessinables par la police du ticket, et sans syntaxe du plan en tête : un texte en
    « # », « [ » ou « > » deviendrait titre, marque ou citation au rendu (`ticket.py`)."""
    manquants = "".join(sorted({c for texte in textes for c in absents(texte)}))
    if manquants:
        raise ErreurContenu(chemin, f"{ident} : caractères non imprimables {manquants!r}")
    if any(texte.lstrip().startswith(SYNTAXE_DU_PLAN) for texte in textes):
        raise ErreurContenu(chemin, f"{ident} : texte en « # », « [ » ou « > » (syntaxe du plan)")


def _uniques(chemin: Path, ids: list[str]) -> None:
    doublons = sorted({i for i in ids if ids.count(i) > 1})
    if doublons:
        raise ErreurContenu(chemin, f"identifiants en double : {', '.join(doublons)}")


def _rotation_en(chemin: Path, brute: object, longueur: int) -> tuple[str, ...]:
    """`langues_en` : facultative ; sinon autant de langues que `langues`, sans doublon."""
    if brute is None:
        return ()
    if not isinstance(brute, list) or len(brute) != longueur:
        raise ErreurContenu(chemin, "« langues_en » : même nombre de langues que « langues »")
    rotation = tuple(str(langue) for langue in brute)
    if len(set(rotation)) < len(rotation):
        raise ErreurContenu(chemin, "« langues_en » : langue en double")
    return rotation


def lire_config(chemin: Path = DOSSIER_GENERAL / "general.md") -> ConfigGeneral:
    entete, _ = lire(chemin)
    langues, eleves = entete.get("langues"), entete.get("eleves")
    if not isinstance(langues, list) or not langues:
        raise ErreurContenu(chemin, "« langues » : liste non vide attendue")
    if not isinstance(eleves, dict):
        raise ErreurContenu(chemin, "« eleves » : table nom → profil attendue")
    ville = str(entete.get("ville") or "").strip()
    fuseau = str(entete.get("fuseau") or "").strip()
    if not ville or not fuseau:
        raise ErreurContenu(chemin, "« ville » et « fuseau » attendus")
    if len(set(map(str, langues))) < len(langues):
        doublons = sorted({str(x) for x in langues if langues.count(x) > 1})
        raise ErreurContenu(chemin, f"langue en double dans la rotation : {', '.join(doublons)}")
    try:
        ZoneInfo(fuseau)
    except (ZoneInfoNotFoundError, ValueError, OSError):  # « Europe » : un dossier
        raise ErreurContenu(chemin, f"fuseau inconnu : {fuseau}") from None
    try:
        origine = date.fromisoformat(str(entete.get("origine")))
        latitude = float(str(entete.get("latitude")))
        longitude = float(str(entete.get("longitude")))
        seuil = int(str(entete.get("seuil_pluie")))
    except ValueError as erreur:
        raise ErreurContenu(chemin, f"origine, coordonnées ou seuil invalides ({erreur})") from None
    if not 0 <= seuil <= 100:
        raise ErreurContenu(chemin, f"seuil de pluie hors de 0 – 100 : {seuil}")
    profils: dict[str, Profil] = {}
    for nom, profil in eleves.items():
        if not isinstance(profil, dict):
            raise ErreurContenu(chemin, f"élève {nom} : « prenom » attendu")
        prenom, autre = profil.get("prenom"), profil.get("mot_de")
        langue = profil.get("langue", LANGUE_PAR_DEFAUT)
        if not isinstance(prenom, str) or not (autre is None or isinstance(autre, str)):
            raise ErreurContenu(chemin, f"élève {nom} : « prenom » / « mot_de » en texte attendu")
        if not prenom.strip():
            raise ErreurContenu(chemin, f"élève {nom} : « prenom » attendu")
        if langue not in LANGUES:
            raise ErreurContenu(chemin, f"élève {nom} : langue inconnue {langue!r} ({LANGUES})")
        profils[str(nom)] = Profil(prenom.strip(), (autre or "").strip() or None, str(langue))
    noms = [texte for p in profils.values() for texte in (p.prenom, p.mot_de or "")]
    _imprimables(chemin, "config", ville, *noms)
    rotation = tuple(str(langue) for langue in langues)
    rotation_en = _rotation_en(chemin, entete.get("langues_en"), len(rotation))
    if rotation_en == () and any(p.langue == "en" for p in profils.values()):
        raise ErreurContenu(chemin, "élève en anglais : « langues_en » attendue")
    return ConfigGeneral(
        ville, latitude, longitude, fuseau, origine, rotation, seuil, profils, rotation_en
    )


def _mots(chemin: Path, langues: tuple[str, ...]) -> tuple[Mot, ...]:
    mots: list[Mot] = []
    for rang, entree in enumerate(_entrees(chemin, "mots")):
        mot = Mot(*[_texte(chemin, entree, cle, rang) for cle in CHAMPS_MOT])
        if mot.langue not in langues:
            raise ErreurContenu(chemin, f"{mot.id} : langue « {mot.langue} » hors de la rotation")
        if any(ord(c) in NIQQUD for c in mot.forme):
            raise ErreurContenu(chemin, f"{mot.id} : hébreu sans niqqud (l'ordre visuel les casse)")
        if max(len(mot.sens), len(mot.question)) > LONGUEUR_MAX:
            raise ErreurContenu(chemin, f"{mot.id} : sens ou question trop long (> {LONGUEUR_MAX})")
        _imprimables(chemin, mot.id, mot.forme, mot.prononciation, mot.sens, mot.question)
        mots.append(mot)
    _uniques(chemin, [m.id for m in mots])
    vides = [langue for langue in langues if not any(m.langue == langue for m in mots)]
    if vides:
        raise ErreurContenu(chemin, f"aucun mot pour : {', '.join(vides)}")
    return tuple(mots)


def _faits(chemin: Path) -> dict[str, Fait]:
    faits: dict[str, Fait] = {}
    for rang, entree in enumerate(_entrees(chemin, "faits")):
        jour = _texte(chemin, entree, "jour", rang)
        if not _MM_JJ.fullmatch(jour) or jour not in JOURS_DE_L_ANNEE:
            raise ErreurContenu(chemin, f"{jour} : jour MM-JJ attendu")
        brut = entree.get("annee")
        if not isinstance(brut, str) or not _ANNEE.fullmatch(brut):
            raise ErreurContenu(chemin, f'{jour} : année entre guillemets attendue (ex. "1791")')
        if jour in faits:
            raise ErreurContenu(chemin, f"{jour} en double")
        texte = _texte(chemin, entree, "texte", rang)
        source = _texte(chemin, entree, "source", rang)
        if len(texte) > LONGUEUR_MAX:
            raise ErreurContenu(chemin, f"{jour} : texte : trop long (> {LONGUEUR_MAX})")
        fait = Fait(jour, int(brut), texte, source)
        _imprimables(chemin, jour, fait.texte)
        faits[jour] = fait
    manquants = [jour for jour in JOURS_DE_L_ANNEE if jour not in faits]
    if manquants:
        raise ErreurContenu(chemin, f"{len(manquants)} jour(s) sans fait, dont {manquants[0]}")
    return faits


def _enigmes(chemin: Path) -> tuple[Enigme, ...]:
    enigmes: list[Enigme] = []
    for rang, entree in enumerate(_entrees(chemin, "enigmes")):
        enigme = Enigme(*[_texte(chemin, entree, cle, rang) for cle in CHAMPS_ENIGME])
        if enigme.type not in TYPES_ENIGME:
            raise ErreurContenu(chemin, f"{enigme.id} : type « {enigme.type} » inconnu")
        if len(enigme.solution) > LONGUEUR_MAX:
            raise ErreurContenu(chemin, f"{enigme.id} : solution : trop long (> {LONGUEUR_MAX})")
        if len(enigme.enonce) > LONGUEUR_ENONCE:
            raise ErreurContenu(chemin, f"{enigme.id} : énoncé : trop long (> {LONGUEUR_ENONCE})")
        _imprimables(chemin, enigme.id, enigme.enonce, enigme.solution)
        enigmes.append(enigme)
    _uniques(chemin, [e.id for e in enigmes])
    vides = [t for t in TYPES_ENIGME if not any(e.type == t for e in enigmes)]
    if vides:
        raise ErreurContenu(chemin, f"aucune énigme de type : {', '.join(vides)}")
    return tuple(enigmes)


def lire_listes(
    config: ConfigGeneral, dossier: Path = DOSSIER_GENERAL, langue: str = LANGUE_PAR_DEFAUT
) -> Listes:
    """Les listes d'une langue d'élève : `dossier` pour le français, `dossier/<langue>/`
    sinon (même format, même validation)."""
    rotation = config.rotation(langue)
    ici = dossier if langue == LANGUE_PAR_DEFAUT else dossier / langue
    return Listes(
        _mots(ici / "mots.md", rotation),
        _faits(ici / "ce-jour-la.md"),
        _enigmes(ici / "enigmes.md"),
        rotation,
    )


def bilan(listes: Listes) -> str:
    par_langue = ", ".join(
        f"{langue} {sum(m.langue == langue for m in listes.mots)}" for langue in listes.rotation
    )
    par_type = ", ".join(f"{t} {sum(e.type == t for e in listes.enigmes)}" for t in TYPES_ENIGME)
    return (
        f"mots {len(listes.mots)} ({par_langue}) · faits {len(listes.faits)} · "
        f"énigmes {len(listes.enigmes)} ({par_type})"
    )


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--dossier", type=Path, default=DOSSIER_GENERAL)
    options = lecteur.parse_args(arguments)
    try:
        config = lire_config(options.dossier / "general.md")
        langues = [LANGUE_PAR_DEFAUT] + (["en"] if config.langues_en else [])
        bilans = [
            (langue, bilan(lire_listes(config, options.dossier, langue))) for langue in langues
        ]
    except (ValueError, OSError) as erreur:
        print(f"partie générale invalide : {erreur}", file=sys.stderr)
        return 1
    for langue, texte in bilans:
        print(texte if langue == LANGUE_PAR_DEFAUT else f"{langue} : {texte}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
