"""`fanout/06_publication` : valider puis publier une carte, sans LLM.

On construit un arbre de préparation (bibliothèque actuelle + sorties du fan-out), on le
valide en entier, on refuse la disparition d'un concept déjà cité par le journal (#20), puis
on échange l'ancien et le nouveau contenu dossier par dossier (`os.replace`, avec retour
arrière si un échange échoue) et on régénère l'index (inv. 13). Le commit reste à l'opérateur.

La bibliothèque est cumulative : un fichier absent du fan-out reste en place. Seule exception,
le renommage (#20) : un concept publié avec `alias: [ancien]` retire `ancien` (et ses
questions, et leur traduction) de la préparation. La traduction (`07_traduction/output/en/`)
se publie de la même façon ; sa structure doit être celle du français (PROF-12).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from freinet.base import ErreurSQLite, concepts_references_en_lecture
from freinet.bibliotheque import (
    RACINE_BIBLIOTHEQUE,
    SURCOUCHES,
    charger,
    concepts_disparus,
    erreurs,
)
from freinet.contenu import lire_concept
from freinet.frontmatter import ErreurContenu
from freinet.index import generer_index
from freinet.langue import libelles
from freinet.sources import Registre, lire_registre
from freinet.temps import maintenant
from freinet.validation import erreurs_contenu

RACINE = Path(__file__).resolve().parent.parent
SOUS_DOSSIERS = ("concepts", "cartes", "quetes", "questions", *SURCOUCHES)
# Où chaque étape du fan-out dépose ses fichiers (sous `<étape>/output/`).
SORTIES = {
    "cartes": "02_carte",
    "quetes": "02_carte",
    "concepts": "03_redaction",
    "questions": "04_questions",
    **{langue: "07_traduction" for langue in SURCOUCHES},
}


# Étapes dont les sorties sont archivées après une publication réussie (un run = une carte).
ETAPES_ARCHIVEES = (
    "00_import",
    "01_cadrage",
    "02_carte",
    "03_redaction",
    "04_questions",
    "05_verification",
    "07_traduction",
)


class RefusPublication(RuntimeError):
    pass


def _fichiers_du_fanout(fanout: Path) -> list[tuple[Path, Path]]:
    """(fichier, chemin relatif dans la bibliothèque) ; refuse les liens symboliques (#45)."""
    trouves = []
    for sous, etape in SORTIES.items():
        sortie = fanout / etape / "output"
        origine = sortie / sous
        if not origine.is_dir():
            continue
        for fichier in sorted(origine.rglob("*")):
            if fichier.is_symlink():
                raise RefusPublication(f"lien symbolique refusé : {fichier}")
            if fichier.is_file() and fichier.suffix == ".md":
                trouves.append((fichier, fichier.relative_to(sortie)))
    return trouves


def preparer(fanout: Path, bibliotheque: Path, cible: Path) -> dict[str, list[str]]:
    """Copie la bibliothèque dans `cible` puis y superpose les sorties du fan-out.

    Rend les chemins relatifs classés en `crees`, `modifies`, `identiques`, `retires`."""
    fichiers = _fichiers_du_fanout(fanout)
    if not fichiers:
        raise RefusPublication(f"aucun fichier .md dans les sorties du fan-out ({fanout})")
    cible.mkdir(parents=True)
    for sous in SOUS_DOSSIERS:
        if (bibliotheque / sous).is_dir():
            shutil.copytree(bibliotheque / sous, cible / sous)
    compte: dict[str, list[str]] = {"crees": [], "modifies": [], "identiques": [], "retires": []}
    for fichier, relatif in fichiers:
        destination = cible / relatif
        if not destination.exists():
            compte["crees"].append(relatif.as_posix())
        elif destination.read_bytes() != fichier.read_bytes():
            compte["modifies"].append(relatif.as_posix())
        else:
            compte["identiques"].append(relatif.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fichier, destination)
    for fichier, relatif in fichiers:
        if relatif.parts[0] == "concepts":
            for ancien in lire_concept(fichier).alias:
                for base in (cible, *(cible / langue for langue in SURCOUCHES)):
                    if (base / "concepts" / f"{ancien}.md").exists():
                        (base / "concepts" / f"{ancien}.md").unlink()
                        shutil.rmtree(base / "questions" / ancien, ignore_errors=True)
                        compte["retires"].append(
                            (base / "concepts" / f"{ancien}.md").relative_to(cible).as_posix()
                        )
    return compte


def _problemes(cible: Path, base: Path | None, registre: Registre) -> list[str]:
    bib = charger(cible)
    problemes = erreurs(bib) + erreurs_contenu(bib, registre)
    for langue in SURCOUCHES:
        if (cible / langue).is_dir():
            traduite = charger(cible, langue)  # structure différente : ErreurContenu, refus
            problemes += [
                f"{langue} : {p}" for p in erreurs_contenu(traduite, registre, libelles(langue))
            ]
    if base is not None and base.is_file():
        for disparu in sorted(concepts_disparus(concepts_references_en_lecture(base), bib)):
            problemes.append(f"{disparu} : concept cité par le journal et disparu (#20)")
    return problemes


def _echanger(bibliotheque: Path, nouvelle: Path) -> None:
    """Remplace chaque sous-dossier et l'index par renommage ; retour arrière si un échec."""
    elements = [*SOUS_DOSSIERS, "index.md"]
    faits: list[tuple[Path, Path | None]] = []
    try:
        for nom in elements:
            actuel, neuf = bibliotheque / nom, nouvelle / nom
            ancien = None
            if actuel.exists():
                ancien = nouvelle / f"{nom}.ancien"
                os.replace(actuel, ancien)
            faits.append((actuel, ancien))
            if neuf.exists():
                os.replace(neuf, actuel)
    except OSError:
        for actuel, ancien in reversed(faits):
            if actuel.is_dir():
                shutil.rmtree(actuel)
            elif actuel.exists():
                actuel.unlink()
            if ancien is not None:
                os.replace(ancien, actuel)
        raise


def publier(
    fanout: Path, bibliotheque: Path, base: Path | None, registre: Registre
) -> tuple[bool, str]:
    """Rend (publié ?, compte rendu). Rien n'est touché si la validation échoue."""
    if not bibliotheque.is_dir():
        return False, _refus([f"bibliothèque introuvable : {bibliotheque}"])
    # Préparée à côté de la bibliothèque (même volume) pour que l'échange soit un renommage.
    nouvelle = bibliotheque.parent / f".{bibliotheque.name}.publication"
    shutil.rmtree(nouvelle, ignore_errors=True)
    try:
        compte = preparer(fanout, bibliotheque, nouvelle)
        problemes = _problemes(nouvelle, base, registre)
        if problemes:
            return False, _refus(problemes)
        (nouvelle / "index.md").write_text(generer_index(charger(nouvelle)), encoding="utf-8")
        _echanger(bibliotheque, nouvelle)
    except (RefusPublication, ErreurContenu, ErreurSQLite, OSError) as erreur:
        return False, _refus([str(erreur)])
    finally:
        shutil.rmtree(nouvelle, ignore_errors=True)
    lignes = ["# Publication", ""]
    for cle, libelle in (
        ("crees", "créés"),
        ("modifies", "modifiés (enrichis)"),
        ("identiques", "réutilisés à l'identique"),
        ("retires", "retirés (renommés, alias conservé)"),
    ):
        lignes.append(f"- {libelle} : {len(compte[cle])}")
        lignes.extend(f"  - {chemin}" for chemin in compte[cle])
    lignes += ["", "Index régénéré. Reste à committer `bibliotheque/`."]
    return True, "\n".join(lignes) + "\n"


def verifier(fanout: Path, bibliotheque: Path, registre: Registre) -> tuple[bool, str]:
    """Contrôle à blanc pour `05_verification` : préparation en dossier temporaire, aucun
    échange, aucune lecture du journal. Rend (sans défaut ?, compte rendu)."""
    with tempfile.TemporaryDirectory() as dossier:
        try:
            preparer(fanout, bibliotheque, Path(dossier) / "bibliotheque")
            problemes = _problemes(Path(dossier) / "bibliotheque", None, registre)
        except (RefusPublication, ErreurContenu, OSError) as erreur:
            problemes = [str(erreur)]
    if problemes:
        return False, "\n".join(
            ["# Vérification : défauts", "", *[f"- {p}" for p in problemes]]
        ) + "\n"
    return True, "# Vérification\n\nAucun défaut de forme : le contenu est publiable.\n"


def archiver(fanout: Path, quand: datetime) -> Path:
    """Range les sorties du run publié dans `fanout/_publies/<horodatage>/` (hors git)."""
    destination = fanout / "_publies" / f"{quand:%Y%m%dT%H%M%SZ}"
    for etape in ETAPES_ARCHIVEES:
        sortie = fanout / etape / "output"
        for element in sorted(sortie.iterdir()) if sortie.is_dir() else []:
            if element.name != ".gitkeep":
                (destination / etape).mkdir(parents=True, exist_ok=True)
                shutil.move(element, destination / etape / element.name)
    return destination


def _refus(problemes: list[str]) -> str:
    return "\n".join(["# Publication refusée", "", *[f"- {p}" for p in problemes]]) + "\n"


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--fanout", type=Path, default=RACINE / "fanout")
    lecteur.add_argument("--bibliotheque", type=Path, default=RACINE_BIBLIOTHEQUE)
    lecteur.add_argument("--base", type=Path, default=RACINE / "data" / "freinet.db")
    lecteur.add_argument(
        "--verifier", action="store_true", help="contrôle à blanc (05) : rien n'est publié"
    )
    options = lecteur.parse_args(arguments)
    try:
        registre = lire_registre()
    except ErreurContenu as erreur:
        print(_refus([str(erreur)]), end="", file=sys.stderr)
        return 1
    if options.verifier:
        sans_defaut, rapport = verifier(options.fanout, options.bibliotheque, registre)
        print(rapport, end="", file=sys.stdout if sans_defaut else sys.stderr)
        return 0 if sans_defaut else 1
    publie, rapport = publier(options.fanout, options.bibliotheque, options.base, registre)
    if publie:
        archive = archiver(options.fanout, maintenant())
        rapport += (
            f"Sorties du run archivées dans `{archive.relative_to(options.fanout.parent)}`.\n"
        )
    sortie = options.fanout / "06_publication" / "output" / "publication.md"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(rapport, encoding="utf-8")
    print(rapport, end="", file=sys.stdout if publie else sys.stderr)
    return 0 if publie else 1


if __name__ == "__main__":
    raise SystemExit(main())
