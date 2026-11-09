"""Deux élèves inscrits à la carte de démonstration (Marius avec sa quête, Lina sans),
tickets de lundi et de mardi remis, et l'API d'ADVIZA servie avec un jeton chacun."""

import http.client
import json
import shutil
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from freinet import eleves, quotidien, rendu
from freinet.adviza_jetons import ConfigAdviza, empreinte
from freinet.api_adviza import ServeurAdviza
from freinet.base import Base
from tests.bibliotheque.demo import DEMO
from tests.general.listes import ecrire_general

LUNDI = date(2026, 1, 5)
MARDI_MATIN = datetime(2026, 1, 6, 7, tzinfo=UTC)
JETON_MARIUS = "jeton-marius-" + "m" * 40
JETON_LINA = "jeton-lina-" + "l" * 40
QUETE = "entendre-une-cadence"
Reponse = tuple[int, dict[str, str], Any]
Site = tuple[ServeurAdviza, Path, dict[str, str]]  # serveur, racine, nom → brainiac_id


def racine_deux_eleves(dossier: Path) -> dict[str, str]:
    """Rend nom → brainiac_id."""
    shutil.copytree(DEMO, dossier / "bibliotheque")
    ids: dict[str, str] = {}
    for nom, quete in (("marius", ["--quete", QUETE]), ("lina", [])):
        assert eleves.main(["--racine", str(dossier), "ajouter", nom, "Europe/Paris"]) == 0
        inscrire = ["--racine", str(dossier), "inscrire", nom, "harmonie-demo", *quete]
        assert eleves.main(inscrire) == 0
        for jour in (LUNDI, LUNDI + timedelta(days=1)):
            instant = f"{jour.isoformat()}T05:00:00+00:00"
            arguments = ["--racine", str(dossier), "--eleve", nom, "--instant", instant]
            assert quotidien.main(arguments) == 0
            rendu.rendre(dossier, nom, jour, None, remis=True)
        with Base(dossier / "data" / "freinet.db") as base:
            eleve = base.brainiac_par_nom(nom)
            assert eleve is not None
            ids[nom] = eleve.brainiac_id
    return ids


def demarrer(racine: Path, ids: dict[str, str], quand: datetime = MARDI_MATIN) -> ServeurAdviza:
    """`general.md` figé dans `racine/general` : le vrai `_config/general/` n'entre pas en jeu."""
    jetons = {empreinte(JETON_MARIUS): ids["marius"], empreinte(JETON_LINA): ids["lina"]}
    general = ecrire_general(racine / "general")
    instance = ServeurAdviza(0, racine, ConfigAdviza(8766, jetons), lambda: quand, general)
    threading.Thread(target=instance.serve_forever, daemon=True).start()
    return instance


def arreter(instance: ServeurAdviza) -> None:
    instance.shutdown()
    instance.server_close()


def appeler(
    instance: ServeurAdviza,
    methode: str,
    chemin: str,
    jeton: str | None = None,
    corps: object = None,
    entetes: dict[str, str] | None = None,
) -> Reponse:
    connexion = http.client.HTTPConnection("127.0.0.1", instance.server_address[1], timeout=5)
    tout: dict[str, str] = {}
    donnees = None
    if jeton is not None:
        tout["Authorization"] = f"Bearer {jeton}"
    if corps is not None:
        donnees = json.dumps(corps).encode("utf-8")
        tout["Content-Type"] = "application/json"
    tout.update(entetes or {})
    connexion.request(methode, chemin, body=donnees, headers=tout)
    reponse = connexion.getresponse()
    brut = reponse.read().decode("utf-8")
    resultat = reponse.status, dict(reponse.getheaders()), json.loads(brut) if brut else None
    connexion.close()
    return resultat
