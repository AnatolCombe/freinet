"""Le rituel du matin (#53), lancé par launchd à 5 h 57 : pour chaque élève, le plan du jour
(avec la phrase du coach), le ticket rendu puis imprimé.

`python -m freinet.matin [--eleve NOM …]` ; sans `--eleve`, tous les élèves. Idempotent : un
ticket déjà remis n'est pas réimprimé, et le plan est figé une fois écrit — un réveil tardif
du Mac qui relance le job ne double rien (rattrapage) ; deux lancements simultanés se suivent
sous le verrou du rituel (`verrou.py`). Un élève en erreur n'arrête pas les
autres. Codes : 0 tout est remis ; 3 au moins un ticket non imprimé (plan et PNG gardés, le
heartbeat de 7 h le signalera) ; 1 au moins une erreur.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from freinet.acces import ConfigRetour, lire_config_retour
from freinet.base import Base, ErreurSQLite
from freinet.imprimante import Cible, lire_imprimante
from freinet.quotidien import PassageImpossible, preparer_jour
from freinet.rendu import ImpressionNonConfirmee, RenduImpossible, rendre
from freinet.temps import date_logique, depuis_iso, maintenant
from freinet.verrou import verrou_du_rituel

RACINE = Path(__file__).resolve().parent.parent
REMIS = ("imprime", "note")


@dataclass(frozen=True)
class Resultat:
    nom: str
    etat: str  # remis, déjà remis, non imprimé, erreur
    detail: str


def noms_eleves(racine: Path) -> list[str]:
    with Base(racine / "data" / "freinet.db") as base:
        eleves = [base.brainiac(b) for b in base.brainiacs()]
    return sorted(e.nom for e in eleves if e is not None)


def matin_d_un_eleve(
    racine: Path,
    nom: str,
    instant: datetime,
    cible: Cible | None,
    config: ConfigRetour | None,
    coach: bool = True,
) -> Resultat:
    try:
        preparer_jour(racine, nom, instant, coach)
        with Base(racine / "data" / "freinet.db") as base:
            eleve = base.brainiac_par_nom(nom)
            if eleve is None:
                raise PassageImpossible(f"élève inconnu : {nom}")
            jour = date_logique(instant, eleve.fuseau)
            statut = base.statut_du_plan(eleve.brainiac_id, jour)
        if statut in REMIS:
            return Resultat(nom, "déjà remis", f"ticket du {jour.isoformat()}")
        png, remis = rendre(racine, nom, jour, cible, config=config)
    except ImpressionNonConfirmee as erreur:
        return Resultat(nom, "non imprimé", str(erreur))
    except (PassageImpossible, RenduImpossible, ValueError, OSError, ErreurSQLite) as erreur:
        return Resultat(nom, "erreur", str(erreur))
    except Exception as bogue:  # un bogue chez un élève n'arrête pas les autres ; pile au journal
        traceback.print_exc(file=sys.stderr)
        return Resultat(nom, "erreur", f"bogue : {type(bogue).__name__}: {bogue}")
    if not remis:
        return Resultat(nom, "non imprimé", f"sans imprimante : {png}")
    return Resultat(nom, "remis", str(png))


def code_de_sortie(resultats: list[Resultat]) -> int:
    etats = {r.etat for r in resultats}
    if "erreur" in etats:
        return 1
    return 3 if "non imprimé" in etats else 0


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--eleve", action="append", help="élève (répétable ; défaut : tous)")
    lecteur.add_argument("--racine", type=Path, default=RACINE)
    lecteur.add_argument("--instant", type=depuis_iso, help="instant ISO 8601 (tests, rattrapage)")
    lecteur.add_argument("--sans-imprimante", action="store_true", help="rendre sans imprimer")
    lecteur.add_argument("--sans-coach", action="store_true", help="phrase par défaut, sans LLM")
    lecteur.add_argument("--sans-qr", action="store_true", help="ticket sans QR ni code")
    options = lecteur.parse_args(arguments)
    try:
        noms = options.eleve or noms_eleves(options.racine)
        config = None if options.sans_qr else lire_config_retour()
    except (ValueError, OSError, ErreurSQLite) as erreur:
        print(f"matin impossible : {erreur}", file=sys.stderr)
        return 1
    cible = None
    if not options.sans_imprimante:
        try:
            cible = lire_imprimante()
        except (ValueError, OSError) as erreur:  # IP pas encore renseignée : on rend quand même
            print(f"sans imprimante : {erreur}", file=sys.stderr)
    instant = options.instant or maintenant()
    try:
        with verrou_du_rituel(options.racine):  # un seul rituel à la fois : jamais de doublon
            resultats = [
                matin_d_un_eleve(
                    options.racine, nom, instant, cible, config, not options.sans_coach
                )
                for nom in noms
            ]
    except OSError as occupe:  # verrou tenu trop longtemps, ou data/ inaccessible
        print(f"matin impossible : {occupe}", file=sys.stderr)
        return 1
    for r in resultats:
        flux = sys.stdout if r.etat in ("remis", "déjà remis") else sys.stderr
        print(f"{r.nom} : {r.etat} — {r.detail}", file=flux)
    if not resultats:
        print("aucun élève (python -m freinet.eleves ajouter …)", file=sys.stderr)
        return 1
    return code_de_sortie(resultats)


if __name__ == "__main__":
    raise SystemExit(main())
