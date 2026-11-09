"""Les entités de la bibliothèque (`_config/schema-fichiers.md`) et leur lecture typée."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from freinet.frontmatter import ErreurContenu, lire, section
from freinet.modele import NATURES

IDENTIFIANT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NATURES_LATERALES = ("analogie", "contraste", "meme_idee")


@dataclass(frozen=True)
class Anecdote:
    texte: str
    source: str


@dataclass(frozen=True)
class Source:
    reference: str  # URL http(s), ou ouvrage « Auteur, Titre (année) »
    titre: str


@dataclass(frozen=True)
class Concept:
    id: str
    titre: str
    domaine: str
    alias: tuple[str, ...]
    lecon: str
    anecdotes: tuple[Anecdote, ...]
    sources: tuple[Source, ...] = ()
    version_longue: str = ""
    analogies: str = ""
    origine: str | None = None
    projet: str | None = None


@dataclass(frozen=True)
class Lateral:
    de: str
    vers: str
    nature: str


def nom_par_defaut(carte_id: str) -> str:
    """« simuler-un-monde » → « Simuler un monde » : le nom d'une carte sans `titre`."""
    return carte_id.replace("-", " ").capitalize()


@dataclass(frozen=True)
class Carte:
    id: str
    concepts: tuple[str, ...]
    prerequis: tuple[tuple[str, str], ...]
    lateraux: tuple[Lateral, ...]
    quetes: tuple[str, ...]
    titre: str | None = None  # sinon dérivé de l'id (`nom_par_defaut`)

    @property
    def nom(self) -> str:
        return self.titre or nom_par_defaut(self.id)


@dataclass(frozen=True)
class Quete:
    id: str
    carte: str
    objectif: str
    chemin: tuple[str, ...]


@dataclass(frozen=True)
class Question:
    id: str
    concept: str
    nature: str
    enonce: str
    reponse: str
    difficulte: int
    explication: str = ""  # facultatif : pourquoi cette réponse, l'erreur fréquente


class _Champs:
    """Accès typé au frontmatter d'un fichier : chaque erreur cite le fichier et le champ."""

    def __init__(self, chemin: Path, donnees: dict[str, object], type_attendu: str) -> None:
        self.chemin = chemin
        self.donnees = donnees
        if donnees.get("type") != type_attendu:
            raise ErreurContenu(
                chemin, f"type attendu {type_attendu!r}, lu {donnees.get('type')!r}"
            )

    def texte(self, cle: str) -> str:
        valeur = self.donnees.get(cle)
        if not isinstance(valeur, str) or not valeur.strip():
            raise ErreurContenu(self.chemin, f"champ {cle!r} : texte non vide attendu")
        return valeur.strip()

    def optionnel(self, cle: str) -> str | None:
        """Texte facultatif : absent ou `null` → None."""
        if self.donnees.get(cle) is None:
            return None
        return self.texte(cle)

    def identifiant(self, cle: str = "id") -> str:
        valeur = self.texte(cle)
        if not IDENTIFIANT.match(valeur):
            raise ErreurContenu(self.chemin, f"identifiant invalide {valeur!r} (kebab-case)")
        return valeur

    def identifiants(self, cle: str) -> tuple[str, ...]:
        valeur = self.donnees.get(cle, [])
        if valeur is None:
            return ()
        if not isinstance(valeur, list):
            raise ErreurContenu(self.chemin, f"champ {cle!r} : liste attendue")
        for element in valeur:
            if not isinstance(element, str) or not IDENTIFIANT.match(element):
                raise ErreurContenu(
                    self.chemin, f"champ {cle!r} : identifiant invalide {element!r}"
                )
        return tuple(valeur)

    def dictionnaires(self, cle: str) -> list[dict[str, object]]:
        valeur = self.donnees.get(cle, [])
        if valeur is None:
            return []
        if not isinstance(valeur, list) or not all(isinstance(v, dict) for v in valeur):
            raise ErreurContenu(self.chemin, f"champ {cle!r} : liste de dictionnaires attendue")
        return [{str(k): v for k, v in element.items()} for element in valeur]


def lire_concept(chemin: Path) -> Concept:
    donnees, corps = lire(chemin)
    champs = _Champs(chemin, donnees, "concept")
    identifiant = champs.identifiant()
    titre, domaine = champs.texte("titre"), champs.texte("domaine")
    alias = champs.identifiants("alias")
    anecdotes = []
    for brute in champs.dictionnaires("anecdotes"):
        texte, source = brute.get("texte"), brute.get("source")
        if not (
            isinstance(texte, str) and texte.strip() and isinstance(source, str) and source.strip()
        ):
            raise ErreurContenu(chemin, "anecdote sans texte ou sans source (inv. 9)")
        anecdotes.append(Anecdote(texte.strip(), source.strip()))
    sources = []
    for brute in champs.dictionnaires("sources"):
        cles = [cle for cle in ("url", "ouvrage") if brute.get(cle) is not None]
        reference = brute.get(cles[0]) if len(cles) == 1 else None
        if not isinstance(reference, str) or not reference.strip():
            raise ErreurContenu(chemin, "source : exactement un `url` ou un `ouvrage` (texte)")
        titre_source = brute.get("titre")
        if titre_source is not None and not isinstance(titre_source, str):
            raise ErreurContenu(chemin, "source : `titre` doit être un texte")
        sources.append(Source(reference.strip(), (titre_source or "").strip()))
    lecon = section(corps, "Leçon")
    if not lecon:
        raise ErreurContenu(chemin, "section « ## Leçon » vide ou absente")
    return Concept(
        identifiant,
        titre,
        domaine,
        alias,
        lecon,
        tuple(anecdotes),
        sources=tuple(sources),
        version_longue=section(corps, "Version longue"),
        analogies=section(corps, "Analogies"),
        origine=champs.optionnel("origine"),
        projet=champs.optionnel("projet"),
    )


def lire_carte(chemin: Path) -> Carte:
    donnees, _corps = lire(chemin)
    champs = _Champs(chemin, donnees, "carte")
    prerequis = []
    brut = donnees.get("prerequis") or []
    if not isinstance(brut, list):
        raise ErreurContenu(chemin, "champ 'prerequis' : liste attendue")
    for paire in brut:
        if (
            not isinstance(paire, list)
            or len(paire) != 2
            or not all(isinstance(x, str) and IDENTIFIANT.match(x) for x in paire)
        ):
            raise ErreurContenu(chemin, f"prérequis invalide {paire!r} (attendu [avant, après])")
        prerequis.append((paire[0], paire[1]))
    lateraux = []
    for lien in champs.dictionnaires("lateraux"):
        de, vers, nature = lien.get("de"), lien.get("vers"), lien.get("nature")
        if not (
            isinstance(de, str)
            and isinstance(vers, str)
            and IDENTIFIANT.match(de)
            and IDENTIFIANT.match(vers)
            and isinstance(nature, str)
            and nature in NATURES_LATERALES
        ):
            raise ErreurContenu(chemin, f"lien latéral invalide {lien!r}")
        lateraux.append(Lateral(de, vers, nature))
    return Carte(
        id=champs.identifiant(),
        concepts=champs.identifiants("concepts"),
        prerequis=tuple(prerequis),
        lateraux=tuple(lateraux),
        quetes=champs.identifiants("quetes"),
        titre=champs.optionnel("titre"),
    )


def lire_quete(chemin: Path) -> Quete:
    donnees, _corps = lire(chemin)
    champs = _Champs(chemin, donnees, "quete")
    return Quete(
        id=champs.identifiant(),
        carte=champs.identifiant("carte"),
        objectif=champs.texte("objectif"),
        chemin=champs.identifiants("chemin"),
    )


def lire_question(chemin: Path) -> Question:
    donnees, _corps = lire(chemin)
    champs = _Champs(chemin, donnees, "question")
    nature = champs.texte("nature")
    if nature not in NATURES:
        raise ErreurContenu(chemin, f"nature de question inconnue {nature!r}")
    difficulte = donnees.get("difficulte")
    if not isinstance(difficulte, int) or isinstance(difficulte, bool) or not 1 <= difficulte <= 5:
        raise ErreurContenu(chemin, "difficulte : entier de 1 à 5 attendu")
    return Question(
        id=champs.identifiant(),
        concept=champs.identifiant("concept"),
        nature=nature,
        enonce=champs.texte("enonce"),
        reponse=champs.texte("reponse"),
        difficulte=difficulte,
        explication=champs.optionnel("explication") or "",
    )
