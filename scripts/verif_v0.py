#!/usr/bin/env python3
"""Vérification V0 (PRD §5), sur une base neuve dans un dossier temporaire :
1. la carte de démonstration est publiée (`06_publication`) ;
2. le plan et le ticket du jour 1 sont rendus ;
3. un retour QR est posté à la vraie page (`freinet.serveur`, en local) ;
4. le plan suivant reflète FSRS : raté, le concept revient ; réussi, il est repoussé (A8) ;
5. le rejeu de `revue` redonne les caches (inv. 4).
`scripts/verif-v0.sh` y ajoute la suite de tests et la couverture (étape 6).
"""

from __future__ import annotations

import contextlib
import http.client
import io
import os
import shutil
import sys
import tempfile
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
os.environ.setdefault("FREINET_SANS_LLM", "1")  # le ticket sort sans LLM (inv. 7)
os.environ.setdefault("FREINET_SANS_RESEAU", "1")  # ni météo : vérification reproductible

from freinet import eleves, quotidien  # noqa: E402
from freinet.acces import ConfigRetour  # noqa: E402
from freinet.base import Base  # noqa: E402
from freinet.bibliotheque import charger  # noqa: E402
from freinet.constantes import lire_regles  # noqa: E402
from freinet.etat import etat_coherent  # noqa: E402
from freinet.frontmatter import lire  # noqa: E402
from freinet.publication import publier  # noqa: E402
from freinet.rendu import rendre  # noqa: E402
from freinet.serveur import ServeurRetour  # noqa: E402
from freinet.sources import lire_registre  # noqa: E402

DEMO = RACINE / "tests" / "donnees" / "bibliotheque"
SORTIES = (("cartes", "02_carte"), ("quetes", "02_carte"), ("concepts", "03_redaction"),
           ("questions", "04_questions"))  # fmt: skip
LUNDI = date(2026, 1, 5)
CONFIG = ConfigRetour("127.0.0.1", 0, "http://localhost")


class Echec(Exception):
    pass


def _verifier(condition: bool, message: str) -> None:
    if not condition:
        raise Echec(message)


def _publier(racine: Path) -> None:
    fanout = racine / "fanout"
    for sous, etape in SORTIES:
        shutil.copytree(DEMO / sous, fanout / etape / "output" / sous)
    bibliotheque = racine / "bibliotheque"
    bibliotheque.mkdir()
    (bibliotheque / "index.md").write_text("vide\n", encoding="utf-8")
    base = racine / "data" / "freinet.db"
    publie, rapport = publier(fanout, bibliotheque, base, lire_registre())
    _verifier(publie, f"publication refusée :\n{rapport}")


def _passage(racine: Path, jour: date) -> dict[str, object]:
    instant = f"{jour.isoformat()}T05:00:00+00:00"
    code = quotidien.main(["--racine", str(racine), "--eleve", "marius", "--instant", instant])
    _verifier(code == 0, f"plan du {jour} non écrit")
    png, remis = rendre(racine, "marius", jour, None, remis=True, config=CONFIG)
    _verifier(png.is_file() and remis, f"ticket du {jour} non rendu")
    entete, _ = lire(racine / "brainiacs" / "marius" / "plans" / f"{jour.isoformat()}.md")
    return entete


def _noter_par_la_page(racine: Path, jour: date, question: str, note: int) -> None:
    sortie = racine / "quotidien" / "03_rendu" / "output" / "marius"
    jeton_clair = (sortie / f"acces-{jour.isoformat()}.txt").read_text(encoding="ascii").split()[0]
    quand = datetime.combine(jour, datetime.min.time(), UTC) + timedelta(hours=7)
    serveur = ServeurRetour(("127.0.0.1", 0), racine, lambda: quand)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        port = serveur.server_address[1]
        connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        entetes = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"http://127.0.0.1:{port}",
        }
        corps = f"question={question}&note={note}"
        connexion.request("POST", f"/r/{jeton_clair}/note", body=corps, headers=entetes)
        statut = connexion.getresponse().status
        connexion.close()
    finally:
        serveur.shutdown()
        serveur.server_close()
    _verifier(statut == 303, f"retour QR refusé (HTTP {statut})")


def scenario(dossier: Path, note: int) -> list[str]:
    """Les concepts révisés le 3e jour, après une note `note` au premier rappel."""
    _publier(dossier)
    ajoute = eleves.main(["--racine", str(dossier), "ajouter", "marius", "Europe/Paris"])
    inscrit = eleves.main(["--racine", str(dossier), "inscrire", "marius", "harmonie-demo"])
    _verifier(ajoute == inscrit == 0, "élève non ajouté ou non inscrit")
    jour1 = _passage(dossier, LUNDI)
    _verifier(jour1.get("nouvelle") == "intervalle", "jour 1 : notion nouvelle attendue")
    jour2 = _passage(dossier, LUNDI + timedelta(days=1))
    items = jour2.get("items")
    if not isinstance(items, list) or len(items) != 1:
        raise Echec("jour 2 : un premier rappel attendu")
    _noter_par_la_page(dossier, LUNDI + timedelta(days=1), str(items[0]["question_id"]), note)
    jour3 = _passage(dossier, LUNDI + timedelta(days=2))
    with Base(dossier / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom("marius")
        if eleve is None:
            raise Echec("élève introuvable")
        bib = charger(dossier / "bibliotheque")
        coherent = etat_coherent(base, eleve.brainiac_id, lire_regles(), bib.canonique)
        _verifier(coherent, "rejeu divergent")
    items3 = jour3.get("items")
    return [str(i["concept_id"]) for i in items3] if isinstance(items3, list) else []


def main() -> int:
    etapes = []
    try:
        with (
            tempfile.TemporaryDirectory() as rate,
            tempfile.TemporaryDirectory() as reussi,
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):  # le détail des commandes n'intéresse que si une étape échoue
            apres_echec = scenario(Path(rate), 1)
            apres_reussite = scenario(Path(reussi), 4)
        etapes.append("carte publiée, tickets des jours 1 à 3 rendus, retours QR postés")
        _verifier("intervalle" in apres_echec, "raté : le concept devait revenir le lendemain")
        _verifier("intervalle" not in apres_reussite, "réussi : le concept devait être repoussé")
        etapes.append("FSRS : raté → revient, réussi → repoussé ; rejeu identique")
    except Echec as echec:
        for etape in etapes:
            print(f"✓ {etape}")
        print(f"✗ {echec}", file=sys.stderr)
        return 1
    for etape in etapes:
        print(f"✓ {etape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
