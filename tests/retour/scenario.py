"""Un élève inscrit à la carte de démonstration, avec son plan du jour et un ticket remis."""

import shutil
from datetime import date
from pathlib import Path

from freinet import eleves, quotidien, rendu
from freinet.acces import Acces, ConfigRetour, acces_du_jour, cle_acces, hacher
from freinet.base import Base
from freinet.base.plans import PlanAcces
from tests.bibliotheque.demo import DEMO

CONFIG = ConfigRetour("127.0.0.1", 8765, "http://freinet.local:8765")
LUNDI = date(2026, 1, 5)


def instant(jour: date, heure: int = 5) -> str:
    return f"{jour.isoformat()}T{heure:02d}:00:00+00:00"


def racine_demo(dossier: Path) -> Path:
    shutil.copytree(DEMO, dossier / "bibliotheque")
    assert eleves.main(["--racine", str(dossier), "ajouter", "marius", "Europe/Paris"]) == 0
    assert eleves.main(["--racine", str(dossier), "inscrire", "marius", "harmonie-demo"]) == 0
    return dossier


def passage(racine: Path, jour: date) -> Acces:
    """Plan du jour, ticket remis (lu à l'écran) ; rend l'accès de sa page."""
    arguments = ["--racine", str(racine), "--eleve", "marius", "--instant", instant(jour)]
    assert quotidien.main(arguments) == 0
    rendu.rendre(racine, "marius", jour, None, remis=True, config=CONFIG)
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom("marius")
        assert eleve is not None
        sortie = racine / "quotidien" / "03_rendu" / "output" / "marius"
        return acces_du_jour(base, eleve.brainiac_id, jour, sortie, cle_acces(racine))


def plan(racine: Path, secret: str) -> PlanAcces:
    with Base(racine / "data" / "freinet.db") as base:
        trouve = base.plan_par_acces(hacher(cle_acces(racine), secret), date(2000, 1, 1))
    assert trouve is not None
    return trouve
