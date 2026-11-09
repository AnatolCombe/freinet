"""`quotidien/03_rendu` : du plan du jour au ticket, puis à l'imprimante.

`python -m freinet.rendu --eleve marius [--jour AAAA-MM-JJ] [--imprimer | --remis]` écrit
`quotidien/03_rendu/output/<élève>/ticket-AAAA-MM-JJ.png` et `.txt`. Avec `--imprimer` (ou
`--imprimante usb|hote[:port]`), il envoie le ticket à la TM-m30II-H et, une fois sa sortie
confirmée par l'imprimante, le marque imprimé : sa notion compte alors comme présentée.
`--remis` marque le ticket comme remis sans imprimer (lu à l'écran, repli). Impression non
confirmée → code 3, le ticket et le plan restent sur disque (repli, #44).

Le ticket porte le QR de la page du retour (ou la page « Aujourd'hui » d'ADVIZA, `QR vers
ADVIZA`) et son code court (`acces.py`, `_config/retour.md`) : le même d'un rendu à l'autre du
jour ; `--nouvel-acces` le renouvelle (l'ancien ticket ne s'ouvre plus) ; `--sans-qr` n'en met
pas.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from freinet.acces import (
    ConfigRetour,
    acces_du_jour,
    cle_acces,
    code_lisible,
    lire_config_retour,
)
from freinet.base import Base, ErreurSQLite
from freinet.bibliotheque import charger
from freinet.imprimante import Cible, envoyer, escpos, imprimante, lire_imprimante
from freinet.rendu_png import png_ticket
from freinet.temps import date_logique, maintenant
from freinet.ticket import Retour, langue_du_plan, lire_ticket, texte_ticket
from freinet.verrou import verrou_du_rituel

RACINE = Path(__file__).resolve().parent.parent
IMPRIMANTE_INJOIGNABLE = 3


class RenduImpossible(LookupError):
    """Rien à rendre (élève inconnu, pas de plan) : message d'une ligne, code 1."""


class ImpressionNonConfirmee(Exception):
    """Le ticket est écrit sur disque, mais sa sortie n'est pas confirmée : code 3."""

    def __init__(self, png: Path, cause: OSError) -> None:
        raison = str(cause) or type(cause).__name__
        super().__init__(f"impression non confirmée ({raison}) : le ticket reste dans {png}")
        self.png = png


def _publier(chemin: Path, contenu: bytes) -> None:
    """Écriture par renommage : un lecteur ne voit jamais un fichier à moitié écrit."""
    descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, suffix=".tmp")
    try:
        with os.fdopen(descripteur, "wb") as fichier:
            fichier.write(contenu)
        os.replace(temporaire, chemin)
    finally:
        Path(temporaire).unlink(missing_ok=True)


def rendre(
    racine: Path,
    nom: str,
    jour: date | None,
    cible: Cible | None,
    remis: bool = False,
    config: ConfigRetour | None = None,
    nouvel_acces: bool = False,
) -> tuple[Path, bool]:
    """Écrit le PNG et le texte du ticket ; l'imprime si `cible` est donnée, ou le marque remis
    sans l'imprimer (`remis`). Avec `config`, le ticket porte le QR et le code court du jour.
    Rend le chemin du PNG et si le ticket a été remis."""
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom(nom)
        if eleve is None:
            raise RenduImpossible(f"élève inconnu : {nom}")
        jour = jour or date_logique(maintenant(), eleve.fuseau)
        plan = racine / "brainiacs" / nom / "plans" / f"{jour.isoformat()}.md"
        if not plan.is_file():
            raise RenduImpossible(
                f"aucun plan le {jour.isoformat()} pour {nom} (python -m freinet.quotidien)"
            )
        sortie = racine / "quotidien" / "03_rendu" / "output" / nom
        sortie.mkdir(parents=True, exist_ok=True)
        retour = None
        if config is not None:
            base.plan_du_jour(eleve.brainiac_id, jour)  # la ligne existe (base restaurée)
            cle = cle_acces(racine)
            acces = acces_du_jour(base, eleve.brainiac_id, jour, sortie, cle, nouvel_acces)
            lien = config.lien_du_qr(acces.jeton)
            retour = Retour(lien, code_lisible(acces.code), config.page_code)
        bib = charger(racine / "bibliotheque", langue_du_plan(plan))
        ticket = lire_ticket(plan, bib, retour)
        image = png_ticket(ticket)
        png = sortie / f"ticket-{jour.isoformat()}.png"
        tampon = io.BytesIO()
        image.save(tampon, format="PNG")
        _publier(png, tampon.getvalue())
        _publier(png.with_suffix(".txt"), texte_ticket(ticket).encode("utf-8"))
        if cible is None and not remis:
            return png, False
        if cible is not None:
            try:
                envoyer(escpos(image), cible)
            except OSError as erreur:
                raise ImpressionNonConfirmee(png, erreur) from erreur
        base.marquer_imprime(eleve.brainiac_id, jour)
    return png, True


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--eleve", required=True)
    lecteur.add_argument("--racine", type=Path, default=RACINE)
    lecteur.add_argument(
        "--jour", type=date.fromisoformat, help="AAAA-MM-JJ (défaut : aujourd'hui)"
    )
    mode = lecteur.add_mutually_exclusive_group()
    mode.add_argument("--imprimer", action="store_true", help="imprimer (_config/imprimante.md)")
    mode.add_argument("--imprimante", type=imprimante, help="imprimer sur « usb » ou hote[:port]")
    mode.add_argument("--remis", action="store_true", help="ticket lu à l'écran, sans imprimer")
    lecteur.add_argument("--sans-qr", action="store_true", help="pas de QR ni de code court")
    lecteur.add_argument(
        "--nouvel-acces", action="store_true", help="nouveau QR et code (révoque l'ancien)"
    )
    options = lecteur.parse_args(arguments)
    try:
        cible = None
        if options.imprimer or options.imprimante:
            cible = options.imprimante or lire_imprimante()
        config = None if options.sans_qr else lire_config_retour()
        with verrou_du_rituel(options.racine):  # jamais en même temps que le rituel du matin
            png, remis = rendre(
                options.racine,
                options.eleve,
                options.jour,
                cible,
                options.remis,
                config,
                options.nouvel_acces,
            )
    except ImpressionNonConfirmee as erreur:
        print(erreur, file=sys.stderr)
        return IMPRIMANTE_INJOIGNABLE
    except (RenduImpossible, ValueError, OSError, ErreurSQLite) as erreur:
        # Élève, plan, bibliothèque, _config ou disque : une ligne, pas de trace.
        print(f"rendu impossible : {erreur}", file=sys.stderr)
        return 1
    print(f"{png} (imprimé)" if remis and cible else f"{png} (remis)" if remis else png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
