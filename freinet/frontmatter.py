"""Lecture des fichiers de contenu : frontmatter YAML + corps Markdown (sans framework)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


class ErreurContenu(ValueError):
    """Un fichier de la bibliothèque est mal formé. Le message cite toujours le fichier."""

    def __init__(self, chemin: Path, message: str) -> None:
        super().__init__(f"{chemin} : {message}")
        self.chemin = chemin


_OUVERTURE = re.compile(r"\A---[ \t]*\n")
_FERMETURE = re.compile(r"^---[ \t]*$", re.MULTILINE)


def lire(chemin: Path) -> tuple[dict[str, object], str]:
    """Rend (frontmatter, corps). Le fichier doit commencer par `---` et fermer le bloc.

    Tolère un BOM UTF-8, les fins de ligne Windows et un `---` final sans retour à la ligne.
    """
    try:
        texte = chemin.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ErreurContenu(chemin, "encodage non UTF-8") from None
    ouverture = _OUVERTURE.match(texte)
    if ouverture is None:
        raise ErreurContenu(chemin, "frontmatter absent (le fichier doit commencer par ---)")
    fermeture = _FERMETURE.search(texte, ouverture.end())
    if fermeture is None:
        raise ErreurContenu(chemin, "frontmatter non fermé")
    try:
        donnees = yaml.safe_load(texte[ouverture.end() : fermeture.start()])
    except yaml.YAMLError as erreur:
        raise ErreurContenu(chemin, f"YAML invalide ({erreur})") from None
    if donnees is None:
        raise ErreurContenu(chemin, "frontmatter vide")
    if not isinstance(donnees, dict):
        raise ErreurContenu(chemin, "le frontmatter doit être un dictionnaire")
    corps = texte[fermeture.end() :].removeprefix("\n")
    return {str(cle): valeur for cle, valeur in donnees.items()}, corps


def section(corps: str, titre: str) -> str:
    """Le texte sous `## titre`, jusqu'au titre de niveau 2 suivant ; vide si absent."""
    lignes = corps.splitlines()
    dedans = False
    retenues: list[str] = []
    for ligne in lignes:
        if ligne.startswith("## "):
            if dedans:
                break
            dedans = ligne[3:].strip() == titre
            continue
        if dedans:
            retenues.append(ligne)
    return "\n".join(retenues).strip()
