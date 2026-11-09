"""Le passage du matin (`quotidien/01` + `02`) : état recalculé → sélection → plan du jour.

`python -m freinet.quotidien --eleve marius` : écrit `brainiacs/<élève>/plans/AAAA-MM-JJ.md`
puis réserve le plan du jour dans la base. Le fichier du plan fait foi : une fois écrit, il est
figé (relancer le rend tel quel, sans recalcul ; un scan entre deux passages ne change pas le
ticket déjà imprimé ; une retouche à la main est conservée) et la base est resynchronisée sur
sa notion `nouvelle` à chaque passage. Pour refaire le plan d'un jour, supprimer le fichier.
La partie générale (`_config/general/`, PROF-8) et la météo du jour sont écrites dans le plan
et figées avec lui ; une liste générale invalide ou une météo absente n'empêchent pas le
ticket (inv. 7) : le plan sort sans elles, l'erreur va sur la sortie d'erreur (journal).
La langue de l'élève (profil de `general.md`, PROF-12) règle la partie générale, le défi, la
consigne du coach et les titres du plan.

`--racine` désigne les données (`bibliotheque/`, `data/`, `brainiacs/`) ; `_config/` est celui
du dépôt.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from freinet.base import Base, ErreurSQLite
from freinet.bibliotheque import charger, manquants
from freinet.coach import contexte, phrase_du_coach
from freinet.constantes import lire_regles
from freinet.dose import lire_dose
from freinet.etat import recalculer
from freinet.frontmatter import lire
from freinet.general import DOSSIER_GENERAL, lire_config, lire_listes
from freinet.langue import LANGUE_PAR_DEFAUT, libelles
from freinet.meteo import meteo_du_jour
from freinet.partie_generale import Partie, partie_du_jour
from freinet.plan import ecrire_plan, phrase_par_defaut
from freinet.selection import notion_de_demain, selectionner
from freinet.temps import date_logique, depuis_iso, maintenant

RACINE = Path(__file__).resolve().parent.parent


class PassageImpossible(LookupError):
    """Rien à préparer pour cet élève : message d'une ligne, code 1."""


def _synchroniser(base: Base, brainiac_id: str, jour: date, chemin: Path) -> None:
    """La base suit la notion `nouvelle` que montre le fichier (restauration, retouche)."""
    entete, _ = lire(chemin)
    nouvelle = entete.get("nouvelle")
    base.fixer_plan(brainiac_id, jour, nouvelle if isinstance(nouvelle, str) else None)


def _promesse(dossier: Path, jour: date) -> str | None:
    """La notion annoncée par le plan de la veille (`demain`, #126), s'il existe."""
    chemin = dossier / "plans" / f"{(jour - timedelta(days=1)).isoformat()}.md"
    if not chemin.is_file():
        return None
    entete, _ = lire(chemin)
    valeur = entete.get("demain")
    return valeur if isinstance(valeur, str) else None


def _general(nom: str, jour: date, dossier_general: Path) -> tuple[str, Partie | None]:
    """La langue de l'élève et la partie générale du jour, ou rien. Décision B (Marius,
    2026-09-30) : une liste cassée (retouche du soir, YAML invalide) ne bloque pas le ticket,
    qui sort sans elle (inv. 7) ; une config illisible le laisse en français (PROF-12)."""
    try:
        general = lire_config(dossier_general / "general.md")
    except (ValueError, OSError) as erreur:  # ErreurContenu est une ValueError
        print(f"partie générale absente : {erreur}", file=sys.stderr)
        return LANGUE_PAR_DEFAUT, None
    langue = general.profil(nom).langue
    try:
        listes = lire_listes(general, dossier_general, langue)
    except (ValueError, OSError) as erreur:
        print(f"partie générale absente : {erreur}", file=sys.stderr)
        return langue, None
    return langue, partie_du_jour(nom, jour, general, listes, meteo_du_jour(jour, general))


def preparer_jour(
    racine: Path,
    nom: str,
    instant: datetime,
    coach: bool = True,
    dossier_general: Path = DOSSIER_GENERAL,
) -> Path:
    """Écrit (une fois) le plan du jour ; `coach` : phrase du LLM, sinon celle par défaut. La
    partie générale (`dossier_general`) s'y ajoute si ses listes sont valides (`_partie`)."""
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom(nom)
        if eleve is None:
            raise PassageImpossible(f"élève inconnu : {nom} (python -m freinet.eleves ajouter …)")
        jour = date_logique(instant, eleve.fuseau)
        dossier = racine / "brainiacs" / nom
        chemin = dossier / "plans" / f"{jour.isoformat()}.md"
        if not chemin.is_file():
            inscriptions = base.inscriptions(eleve.brainiac_id)
            langue, partie = _general(nom, jour, dossier_general)
            lib = libelles(langue)
            bib = charger(racine / "bibliotheque", langue)
            if not any(i.carte_id in bib.cartes for i in inscriptions):
                raise PassageImpossible(
                    f"aucune carte inscrite pour {nom} (python -m freinet.eleves inscrire …)"
                )
            if langue != LANGUE_PAR_DEFAUT:
                reste = manquants(bib, [i.carte_id for i in inscriptions])
                if reste:  # le ticket sort quand même, ces textes en français (inv. 7)
                    print(
                        f"traduction {langue} manquante : {len(reste)} fichier(s), "
                        f"dont {', '.join(reste[:3])}",
                        file=sys.stderr,
                    )
            regles, dose = lire_regles(), lire_dose()
            etats = recalculer(base, eleve.brainiac_id, regles, bib.canonique)
            arguments = (
                bib,
                etats,
                base.revues(eleve.brainiac_id),
                inscriptions,
                eleve.brainiac_id,
                eleve.fuseau,
                eleve.dosage,
                dose,
                instant,
                base.concepts_presentes(eleve.brainiac_id, avant=jour),
                base.concepts_joker(eleve.brainiac_id, avant=jour),
            )
            promesse = _promesse(dossier, jour)
            selection = selectionner(*arguments, promesse=promesse, libelles=lib)
            if selection.reprise and promesse:
                demain: str | None = promesse  # reprise : la promesse est reportée
            else:
                demain = notion_de_demain(*arguments, aujourdhui=selection)
            phrase = phrase_par_defaut(selection, lib)
            if coach:
                phrase = phrase_du_coach(contexte(selection), phrase, systeme=lib.coach_systeme)
            chemin = ecrire_plan(selection, bib, dossier, phrase, partie, demain, langue)
        _synchroniser(base, eleve.brainiac_id, jour, chemin)
    return chemin


def _instant(texte: str) -> datetime:
    try:
        return depuis_iso(texte)
    except ValueError as erreur:
        raise argparse.ArgumentTypeError(
            f"instant ISO 8601 avec fuseau attendu ({erreur})"
        ) from None


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--eleve", required=True)
    lecteur.add_argument("--racine", type=Path, default=RACINE)
    lecteur.add_argument(
        "--instant", type=_instant, help="instant ISO 8601 avec fuseau (tests, rattrapage)"
    )
    lecteur.add_argument("--sans-coach", action="store_true", help="phrase par défaut, sans LLM")
    options = lecteur.parse_args(arguments)
    try:
        chemin = preparer_jour(
            options.racine, options.eleve, options.instant or maintenant(), not options.sans_coach
        )
    except (PassageImpossible, ValueError, OSError, ErreurSQLite) as erreur:
        # Erreurs attendues (élève, bibliothèque, _config, disque, base verrouillée) : une ligne.
        # Un KeyError ou un IndexError est un bogue : il remonte avec sa pile.
        print(f"passage du matin impossible : {erreur}", file=sys.stderr)
        return 1
    print(chemin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
