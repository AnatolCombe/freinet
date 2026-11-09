"""`quotidien/02_plan` : le plan du jour, neutre et modifiable, que chaque canal met en forme (B4).

Le frontmatter porte les items à noter (page QR, #16) ; le corps se lit tel quel. La phrase du
coach a toujours une valeur par défaut : le ticket sort sans LLM (inv. 7).
Avec une `Partie` (PROF-8), la météo et le mot de l'autre précèdent la phrase du coach ; mot du
jour, ce jour-là, énigme et notes suivent la quête, et la solution de l'énigme va au pli
(`solution_enigme`). Le plan d'un élève anglophone porte `langue: en` et ses titres en
anglais (PROF-12).
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from datetime import date
from pathlib import Path

import yaml

from freinet.bibliotheque import Bibliotheque
from freinet.langue import FR, LANGUE_PAR_DEFAUT, Libelles, libelles
from freinet.partie_generale import Partie
from freinet.selection import Item, Selection

# Partie générale (PROF-8), relue par `ticket.py` : marques de ligne, pli. Les titres et les
# phrases sont dans la langue de l'élève (`langue.py`, PROF-12) ; le plan porte sa langue
# (`langue:`, absente = français, pour qu'un plan français ne change pas d'un octet).
CLE_LANGUE = "langue"
MARQUE_ECRIRE = "écrire"
MARQUE_CADRE = "cadre"
MARQUE_SEPARATION = "séparation"
CLE_SOLUTION = "solution_enigme"
LIGNES_MOT_DE = 2
LIGNES_NOTES = 5


def phrase_par_defaut(selection: Selection, lib: Libelles = FR) -> str:
    return lib.phrase_reprise if selection.reprise else lib.phrase_defaut


def _ligne(texte: str) -> str:
    """Une seule ligne : un retour à la ligne ne crée ni faux titre ni sortie de citation."""
    return " ".join(texte.split())


def _titre(bib: Bibliotheque, concept_id: str) -> str:
    concept = bib.concepts.get(concept_id)
    return concept.titre if concept else concept_id


def _items(selection: Selection) -> list[Item]:
    items = list(selection.revisions)
    if selection.nouvelle and selection.nouvelle.pre_test:
        items.append(selection.nouvelle.pre_test)
    return items


def _paragraphes(textes: list[str]) -> list[str]:
    """Chaque texte en paragraphe à part (ligne vide avant) : le ticket ne les joint pas."""
    lignes: list[str] = []
    for texte in textes:
        lignes += ["", _ligne(texte)]
    return lignes


def _tete(partie: Partie, lib: Libelles) -> list[str]:
    """Avant la phrase du coach : la météo, puis le mot de l'autre à écrire au stylo."""
    lignes: list[str] = []
    if partie.meteo:
        lignes += ["", f"## {lib.meteo} · {_ligne(partie.ville)}"]
        lignes += _paragraphes(partie.meteo.lignes(lib))
    if partie.mot_de:
        lignes += ["", f"## {lib.mot_de} {_ligne(partie.mot_de)}"]
        lignes += ["", f"[{MARQUE_ECRIRE} : {LIGNES_MOT_DE}]"]
    return lignes


def _pied(partie: Partie, jour: date, lib: Libelles) -> list[str]:
    """Après la partie prof : mot du jour, ce jour-là, énigme (solution au pli), notes."""
    mot, fait, enigme = partie.bloc.mot, partie.bloc.fait, partie.bloc.enigme
    langue_du_mot = lib.langues_du_mot.get(mot.langue, mot.langue.capitalize())
    type_enigme = lib.types_enigme.get(enigme.type, enigme.type.capitalize())
    lignes = ["", f"[{MARQUE_SEPARATION}]"]
    lignes += ["", f"## {lib.mot_du_jour.format(langue=langue_du_mot)}"]
    lignes += _paragraphes([f"{mot.forme} [{mot.prononciation}]", mot.sens, f"→ {mot.question}"])
    lignes += ["", f"## {lib.ce_jour.format(date=lib.jour_du_mois(jour))}"]
    lignes += _paragraphes([f"{lib.annee(fait.annee)} : {fait.texte}"])
    titre_enigme = lib.enigme.format(jour=lib.jours[jour.weekday()], type=type_enigme)
    lignes += ["", f"## {titre_enigme}"]
    lignes += _paragraphes([enigme.enonce])
    lignes += ["", f"## {lib.notes}", "", f"[{MARQUE_CADRE} : {LIGNES_NOTES}]"]
    return lignes


def plan_markdown(
    selection: Selection,
    bib: Bibliotheque,
    phrase: str,
    partie: Partie | None = None,
    demain: str | None = None,
    langue: str = LANGUE_PAR_DEFAUT,
) -> str:
    lib = libelles(langue)
    entete: dict[str, object] = {
        "type": "plan",
        "jour": selection.jour.isoformat(),
        "brainiac_id": selection.brainiac_id,
        "graine": selection.graine,
        "reprise": selection.reprise,
        "nouvelle": selection.nouvelle.concept_id if selection.nouvelle else None,
        "items": [
            {"question_id": i.question_id, "concept_id": i.concept_id, "nature": i.nature}
            for i in _items(selection)
        ],
        "anecdote": (
            {"concept_id": selection.anecdote.concept_id, "source": selection.anecdote.source}
            if selection.anecdote
            else None
        ),
    }
    if langue != LANGUE_PAR_DEFAUT:
        entete[CLE_LANGUE] = langue
    if demain:
        entete["demain"] = demain
    if partie:
        entete["prenom"] = partie.prenom
        entete["general"] = {
            "mot": partie.bloc.mot.id,
            "fait": partie.bloc.fait.jour,
            "enigme": partie.bloc.enigme.id,
            "meteo": partie.meteo is not None,
        }
        entete[CLE_SOLUTION] = _ligne(partie.bloc.enigme.solution)
    lignes = [
        "---",
        yaml.safe_dump(entete, allow_unicode=True, sort_keys=False).rstrip("\n"),
        "---",
        "",
        f"# Plan du {selection.jour.isoformat()}",
        *(_tete(partie, lib) if partie else []),
        "",
        f"> {_ligne(phrase)}",
    ]
    if selection.fil_ariane:
        lignes += ["", _ligne(selection.fil_ariane)]
    if selection.anecdote:
        lignes += ["", f"## {lib.anecdote}", "", selection.anecdote.texte]
    if selection.revisions:
        lignes += ["", f"## {lib.revisions}", ""]
        lignes += [f"{n}. {_ligne(item.enonce)}" for n, item in enumerate(selection.revisions, 1)]
    if selection.nouvelle:
        lignes += ["", f"## {lib.nouveau} · {selection.nouvelle.titre}", ""]
        if selection.nouvelle.pre_test:
            enonce = _ligne(selection.nouvelle.pre_test.enonce)
            lignes += [f"{lib.avant_de_lire} : {enonce}", ""]
        lignes.append(selection.nouvelle.lecon)
    if demain:
        lignes += ["", f"## {lib.demain}", "", _ligne(_titre(bib, demain))]
    if selection.serendipite:
        s = selection.serendipite
        de, vers = _titre(bib, s.de), _titre(bib, s.vers)
        nature = lib.natures.get(s.nature, s.nature.replace("_", " "))
        lignes += ["", f"## {lib.serendipite}", "", f"{de} ~ {vers} ({nature})"]
    if selection.defi:
        lignes += ["", f"## {lib.defi}", "", _ligne(selection.defi)]
    if selection.quete:
        q = selection.quete
        lignes += ["", f"## {lib.quete}", "", f"{q.objectif} : {q.acquis}/{q.total}"]
    if partie:
        lignes += _pied(partie, selection.jour, lib)
    return "\n".join(lignes) + "\n"


def ecrire_plan(
    selection: Selection,
    bib: Bibliotheque,
    dossier_eleve: Path,
    phrase: str,
    partie: Partie | None = None,
    demain: str | None = None,
    langue: str = LANGUE_PAR_DEFAUT,
) -> Path:
    """Publie le plan du jour s'il n'existe pas encore et rend le chemin du plan en place.

    Publication par lien dur d'un fichier temporaire complet : un lecteur (page QR, rendu) ne
    voit jamais un fichier à moitié écrit, et de deux passages simultanés le premier gagne, sans
    que l'autre le remplace. Le plan est lisible par son seul propriétaire (`mkstemp`, inv. 11).
    """
    chemin = dossier_eleve / "plans" / f"{selection.jour.isoformat()}.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, suffix=".tmp")
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
            fichier.write(plan_markdown(selection, bib, phrase, partie, demain, langue))
        with contextlib.suppress(FileExistsError):
            os.link(temporaire, chemin)
    finally:
        Path(temporaire).unlink(missing_ok=True)
    return chemin
