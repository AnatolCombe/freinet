"""`quotidien/03_rendu`, partie neutre : le ticket du jour, lu dans le plan qui fait foi (B4).

Le plan se relit tel quel (une retouche à la main passe sur le ticket) ; la bibliothèque ne
sert qu'aux réponses du pli (#14), repliées sous un pointillé. Tout texte est nettoyé des
caractères de contrôle, et une source web n'est imprimée que par son nom d'hôte (#45).
`texte_ticket` donne la version texte (48 colonnes, police A) : référence des tests (#33)
et repli lisible sans imprimante.
"""

from __future__ import annotations

import re
import textwrap
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from freinet.bibliotheque import Bibliotheque
from freinet.frontmatter import ErreurContenu, lire
from freinet.langue import FR, LANGUE_PAR_DEFAUT, Libelles, libelles
from freinet.plan import (
    CLE_LANGUE,
    CLE_SOLUTION,
    MARQUE_CADRE,
    MARQUE_ECRIRE,
    MARQUE_SEPARATION,
)

LARGEUR_TEXTE = 48
_NUMERO = re.compile(r"^(\d+)\. (.*)$")
_PROGRESSION = re.compile(r"^(.*) : (\d+)/(\d+)$")
_ESPACES = re.compile(r" {2,}")
LIGNES_MAX = 10  # des pointillés ou un cadre retouchés à « 99 » ne vident pas le rouleau
_MARQUE = re.compile(rf"^\[({MARQUE_ECRIRE}|{MARQUE_CADRE}) : ([1-9]\d?)\]$")
_GENRE_MARQUE = {MARQUE_ECRIRE: "ecrire", MARQUE_CADRE: "cadre"}


@dataclass(frozen=True)
class Bloc:
    """Un élément du ticket : `titre`, `citation`, `texte`, `question` (numérotée) ou
    `pre_test` (avant la leçon), chacune avec une ligne pour répondre au stylo, `source`,
    `avertissement`, `quete` (avec sa barre de progression), `ecrire` (`numero` lignes de
    pointillés), `cadre` (un cadre vide de `numero` lignes) ou `separation`."""

    genre: str
    texte: str
    numero: int | None = None
    progression: tuple[int, int] | None = None


@dataclass(frozen=True)
class Reponse:
    etiquette: str
    texte: str


@dataclass(frozen=True)
class Retour:
    """Comment noter le ticket : le QR (lien avec jeton), ou le code court à taper sur
    `page_code` (#34). Le jeton n'est jamais écrit en clair ailleurs que dans le QR."""

    lien: str
    code: str
    page_code: str

    def consigne(self, lib: Libelles = FR) -> str:
        return lib.consigne.format(code=self.code, page=self.page_code)


@dataclass(frozen=True)
class Ticket:
    jour: date
    blocs: tuple[Bloc, ...]
    reponses: tuple[Reponse, ...]
    retour: Retour | None = None
    prenom: str | None = None
    libelles: Libelles = FR


_ESPACES_INSECABLES = frozenset("\u00a0\u202f")  # typographie française : « ! » reste collé


def propre(texte: str) -> str:
    """Composé (NFC), sans caractère de contrôle ni de format (un octet ESC/POS glissé dans un
    texte piloterait l'imprimante), trait d'union conditionnel retiré, espaces ramenées à une
    seule ; les espaces insécables restent."""
    texte = unicodedata.normalize("NFC", texte).replace("\u00ad", "")
    sans = "".join(
        " "
        if unicodedata.category(c).startswith("C") or (c.isspace() and c not in _ESPACES_INSECABLES)
        else c
        for c in texte
    )
    return _ESPACES.sub(" ", sans).strip(" ")


def source_lisible(source: str) -> str:
    """Une URL n'est imprimée que par son nom d'hôte (#45) ; une référence reste telle quelle."""
    morceaux = urlsplit(source.strip())
    if morceaux.scheme in ("http", "https"):
        return propre(morceaux.hostname or "").removeprefix("www.") or "source web"
    return propre(source)


def date_longue(jour: date, lib: Libelles = FR) -> str:
    return lib.date_longue(jour)


def _libelles(chemin: Path, entete: dict[str, object]) -> Libelles:
    """La langue du plan (`langue:`, absente = français, PROF-12)."""
    try:
        return libelles(str(entete.get(CLE_LANGUE) or LANGUE_PAR_DEFAUT))
    except ValueError as erreur:
        raise ErreurContenu(chemin, str(erreur)) from None


def langue_du_plan(chemin: Path) -> str:
    """La langue d'un plan (`langue:`, absente = français) : celle de sa bibliothèque."""
    entete, _ = lire(chemin)
    return _libelles(chemin, entete).code


def _jour(chemin: Path, valeur: object) -> date:
    try:
        return date.fromisoformat(str(valeur))
    except ValueError:
        raise ErreurContenu(chemin, f"jour invalide : {valeur!r}") from None


def _reponses(entete: dict[str, object], bib: Bibliotheque, lib: Libelles) -> tuple[Reponse, ...]:
    items = entete.get("items")
    reponses: list[Reponse] = []
    numero = 0
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        nature = item.get("nature")
        if nature != "pre_test":
            numero += 1
        question = bib.questions.get(str(item.get("question_id")))
        if question is None:
            continue  # question retirée de la bibliothèque : pas de réponse à imprimer
        etiquette = lib.avant_de_lire if nature == "pre_test" else str(numero)
        reponses.append(Reponse(etiquette, propre(question.reponse)))
    return tuple(reponses)


def source_anecdote(entete: dict[str, object]) -> str | None:
    """La source de l'anecdote du plan, telle que le ticket l'imprime (#45) ; lue aussi par
    l'API ADVIZA."""
    anecdote = entete.get("anecdote")
    if isinstance(anecdote, dict) and anecdote.get("source"):
        return source_lisible(str(anecdote["source"]))
    return None


def _concepts_du_jour(entete: dict[str, object], bib: Bibliotheque) -> set[str]:
    items = entete.get("items")
    concepts = (
        {str(i.get("concept_id")) for i in items if isinstance(i, dict)}
        if isinstance(items, list)
        else set()
    )
    if entete.get("nouvelle"):
        concepts.add(str(entete["nouvelle"]))
    return {bib.canonique(c) for c in concepts}


def _solution(entete: dict[str, object], lib: Libelles) -> tuple[Reponse, ...]:
    """La solution de l'énigme du jour, imprimée dans le pli après les réponses."""
    solution = entete.get(CLE_SOLUTION)
    texte = propre(str(solution)) if solution is not None else ""
    return (Reponse(lib.etiquette_enigme, texte),) if texte else ()


def _prenom(entete: dict[str, object]) -> str | None:
    return propre(str(entete.get("prenom") or "")) or None


def _en_tete(section: str, lib: Libelles) -> bool:
    """La météo et le mot de l'autre précèdent la phrase du coach : elle y reste une citation."""
    return section.startswith(lib.meteo) or section.startswith(lib.mot_de)


def lire_ticket(chemin: Path, bib: Bibliotheque, retour: Retour | None = None) -> Ticket:
    """Le ticket d'un plan écrit par `02_plan` (ou retouché à la main). Les questions ne sont
    reconnues que sous « Révisions », le pré-test que sous « Nouveau · … » : ailleurs, une leçon
    en étapes numérotées reste du texte."""
    entete, corps = lire(chemin)
    lib = _libelles(chemin, entete)
    jour = _jour(chemin, entete.get("jour"))
    source = source_anecdote(entete)
    blocs: list[Bloc] = []
    section = ""
    paragraphe: list[str] = []

    def ajouter(bloc: Bloc) -> None:
        if bloc.texte:  # une ligne vide après nettoyage n'imprime rien
            blocs.append(bloc)

    def fermer_paragraphe() -> None:
        if paragraphe:
            ajouter(Bloc("texte", propre(" ".join(paragraphe))))
            paragraphe.clear()

    def fermer_section() -> None:
        fermer_paragraphe()
        if section == lib.anecdote and source:
            ajouter(Bloc("source", lib.source.format(source=source)))

    for ligne in corps.splitlines():
        ligne = ligne.rstrip()
        if ligne.startswith("# "):
            continue  # le titre du plan : le ticket imprime sa propre date
        if ligne.startswith("## "):
            fermer_section()
            section = propre(ligne[3:])
            ajouter(Bloc("titre", section))
        elif not ligne.strip():
            fermer_paragraphe()
        elif ligne == f"[{MARQUE_SEPARATION}]":
            fermer_paragraphe()
            ajouter(Bloc("separation", MARQUE_SEPARATION))
        elif marque := _MARQUE.match(ligne):
            fermer_paragraphe()
            nombre = min(int(marque.group(2)), LIGNES_MAX)
            ajouter(Bloc(_GENRE_MARQUE[marque.group(1)], marque.group(1), nombre))
        elif (not section or _en_tete(section, lib)) and ligne.startswith("> "):
            fermer_section()
            section = ""  # la phrase du coach ferme la tête : la suite n'est plus la météo
            ajouter(Bloc("citation", propre(ligne[2:])))
        elif section == lib.revisions and (numero := _NUMERO.match(ligne)):
            fermer_paragraphe()
            ajouter(Bloc("question", propre(numero.group(2)), int(numero.group(1))))
        elif section.startswith(f"{lib.nouveau} · ") and ligne.startswith(
            f"{lib.avant_de_lire} : "
        ):
            fermer_paragraphe()
            ajouter(Bloc("pre_test", propre(ligne.removeprefix(f"{lib.avant_de_lire} : "))))
        elif section == lib.quete and (progression := _PROGRESSION.match(ligne)):
            fermer_paragraphe()
            acquis, total = int(progression.group(2)), int(progression.group(3))
            ajouter(Bloc("quete", propre(progression.group(1)), None, (acquis, total)))
        else:
            paragraphe.append(ligne)
    fermer_section()
    finance = any(
        bib.concepts[c].domaine == "finance"
        for c in _concepts_du_jour(entete, bib)
        if c in bib.concepts
    )
    if finance:  # inv. 9, B26 : le ticket n'imprime que la leçon, l'avertissement vient ici
        ajouter(Bloc("avertissement", lib.avertissement_finance.capitalize() + "."))
    reponses = _reponses(entete, bib, lib) + _solution(entete, lib)
    return Ticket(jour, tuple(blocs), reponses, retour, _prenom(entete), lib)


def etiquette(reponse: Reponse) -> str:
    return f"{reponse.etiquette}. " if reponse.etiquette.isdigit() else f"{reponse.etiquette} : "


def barre(acquis: int, total: int, largeur: int = 20) -> str:
    pleins = round(largeur * acquis / total) if total > 0 else 0
    pleins = max(0, min(largeur, pleins))
    return "▓" * pleins + "░" * (largeur - pleins) + f" {acquis}/{total}"


def _envelopper(texte: str, debut: str = "", suite: str = "") -> list[str]:
    return textwrap.wrap(texte, LARGEUR_TEXTE, initial_indent=debut, subsequent_indent=suite) or [
        debut.rstrip()
    ]


def texte_ticket(ticket: Ticket) -> str:
    """Le ticket en texte, 48 colonnes : même contenu, même ordre que le bitmap."""
    lib = ticket.libelles
    if ticket.prenom:
        entete = [*_envelopper(f"FREINET · {ticket.prenom}"), date_longue(ticket.jour, lib)]
    else:
        entete = [f"FREINET · {date_longue(ticket.jour, lib)}"]
    lignes = [*entete, "=" * LARGEUR_TEXTE]
    for bloc in ticket.blocs:
        if bloc.genre == "titre":
            titre = bloc.texte.upper()
            lignes += ["", *_envelopper(titre), "-" * min(len(titre), LARGEUR_TEXTE)]
        elif bloc.genre == "citation":
            lignes += _envelopper(bloc.texte, "│ ", "│ ")
        elif bloc.genre == "question":
            lignes += _envelopper(bloc.texte, f"{bloc.numero}. ", "   ")
            lignes.append("   " + "_" * (LARGEUR_TEXTE - 3))
        elif bloc.genre == "pre_test":
            lignes += _envelopper(bloc.texte, f"{lib.avant_de_lire} : ", "   ")
            lignes.append("   " + "_" * (LARGEUR_TEXTE - 3))
        elif bloc.genre == "quete" and bloc.progression is not None:
            lignes += _envelopper(bloc.texte)
            lignes.append(barre(*bloc.progression))
        elif bloc.genre == "ecrire" and bloc.numero:
            lignes += [". " * (LARGEUR_TEXTE // 2 - 1) + "."] * bloc.numero
        elif bloc.genre == "cadre" and bloc.numero:
            interieur = LARGEUR_TEXTE - 2
            lignes.append("┌" + "─" * interieur + "┐")
            lignes += ["│" + " " * interieur + "│"] * bloc.numero
            lignes.append("└" + "─" * interieur + "┘")
        elif bloc.genre == "separation":
            lignes += ["", "=" * LARGEUR_TEXTE]
        else:
            lignes += _envelopper(bloc.texte)
    if ticket.retour:
        lignes += ["", lib.noter, *_envelopper(ticket.retour.consigne(lib))]
    if ticket.reponses:
        lignes += ["", lib.plier, lib.reponses.upper()]
        for reponse in ticket.reponses:
            lignes += _envelopper(reponse.texte, etiquette(reponse), "   ")
    return "\n".join(lignes) + "\n"
