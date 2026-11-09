"""API privée d'ADVIZA (contrat v1, PROF-A) : ADVIZA est l'interface de FREINET.

Servie par le processus de la page du QR (`python -m freinet.serveur`), sur un second port
qui n'écoute que `127.0.0.1` : ADVIZA tourne sur le même Mac. Lectures nommées (`LECTURES`,
JSON, `adviza_lectures.py`), plus `aujourdhui/<AAAA-MM-JJ>` dans la fenêtre du QR (PROF-A4).
`Authorization: Bearer <jeton>` : chaque jeton ouvre un seul élève (`_config/adviza.md`) et
aucune route ne prend d'élève en paramètre. Défenses héritées de la page du QR (délais,
connexions bornées, journal sans adresse ni en-têtes), plus : client et Host de bouclage
seulement, requêtes de navigateur (`Origin`, `Sec-Fetch-Site`) refusées, réponses `no-store`.
Actions nommées `POST /adviza/actions/<nom>` (liste fermée, `Idempotency-Key`, corps JSON borné
avant lecture, `adviza_actions.py`) : ADVIZA les appelle, FREINET reste seul à écrire dans sa
base (PRO-8).
"""

from __future__ import annotations

import ipaddress
import json
import re
import sys
import threading
from collections.abc import Callable
from datetime import date, datetime
from functools import partial
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from freinet import adviza_actions as actions
from freinet import adviza_lectures as lectures
from freinet.adviza_jetons import ConfigAdviza, lire_config_adviza
from freinet.base import Base, ErreurSQLite
from freinet.frontmatter import ErreurContenu
from freinet.general import DOSSIER_GENERAL
from freinet.retour import EnvoiConcurrent, RetourRefuse
from freinet.serveur import Gestionnaire, ServeurRetour
from freinet.temps import maintenant

ECOUTE = "127.0.0.1"
HOTES = frozenset({"127.0.0.1", "localhost"})
ENTETES_JSON = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}
METHODES = "GET, POST"  # les autres répondent 405, défenses passées
Lecture = Callable[[Base, lectures.Contexte], lectures.Json]
LECTURES: dict[str, Lecture] = {
    "/adviza/etat": lectures.etat,
    "/adviza/aujourdhui": lectures.aujourdhui,
    "/adviza/cartes": lectures.cartes,
    "/adviza/catalogue": lectures.catalogue,
}
_ACTION = re.compile(r"/adviza/actions/([a-z_]{1,32})\Z")
_CLE = re.compile(r"[A-Za-z0-9:._-]{1,128}")  # ADVIZA : `<id carte>:<version>`
_LONGUEUR = re.compile(r"[0-9]{1,9}")
# Corps d'une action, borné avant toute lecture : la plus grande requête du contrat (`noter`)
# tient en moins de 300 octets ; 4 Kio laissent de la marge sans exposer la mémoire.
CORPS_MAX = 4096
_CONCEPT = re.compile(r"/adviza/concept/([a-z0-9]+(?:-[a-z0-9]+)*)\Z")  # `contenu.IDENTIFIANT`
_JOUR = re.compile(r"/adviza/aujourdhui/(\d{4}-\d{2}-\d{2})\Z", re.ASCII)  # PROF-A4


class RequeteRefusee(Exception):
    """En-têtes ou corps d'une action refusés avant tout traitement : la clé reste libre."""

    def __init__(self, statut: HTTPStatus, motif: str) -> None:
        super().__init__(motif)
        self.statut, self.motif = statut, motif


class GestionnaireAdviza(Gestionnaire):
    server: ServeurAdviza

    def _json(self, statut: HTTPStatus, corps: lectures.Json, rejoue: bool = False) -> None:
        donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8")
        self.send_response(statut)
        for cle, valeur in ENTETES_JSON.items():
            self.send_header(cle, valeur)
        if statut == HTTPStatus.UNAUTHORIZED:
            self.send_header("WWW-Authenticate", "Bearer")
        if statut == HTTPStatus.METHOD_NOT_ALLOWED:
            self.send_header("Allow", METHODES)
        if rejoue:
            self.send_header("Idempotent-Replayed", "true")
        if statut == HTTPStatus.SERVICE_UNAVAILABLE:
            self.send_header("Retry-After", "1")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        if self.command != "HEAD":  # HEAD : les en-têtes seuls
            self.wfile.write(donnees)

    def _refuser(self, statut: HTTPStatus, motif: str) -> None:
        self._json(statut, {"contrat": lectures.CONTRAT, "ok": False, "motif": motif})

    def _client_de_bouclage(self) -> bool:
        return ipaddress.ip_address(self.client_address[0]).is_loopback

    def _eleve(self) -> str | None:
        """Le `brainiac_id` du jeton, défenses passées ; `None` = refus déjà envoyé."""
        if not self._client_de_bouclage():
            self._refuser(HTTPStatus.FORBIDDEN, "bouclage seulement")
            return None
        if (urlsplit(f"//{self.headers.get('Host', '')}").hostname or "") not in HOTES:
            self._refuser(HTTPStatus.MISDIRECTED_REQUEST, "adresse inattendue")
            return None
        if "Origin" in self.headers or "Sec-Fetch-Site" in self.headers:
            self._refuser(HTTPStatus.FORBIDDEN, "navigateur refusé")
            return None
        schema, _, jeton = self.headers.get("Authorization", "").partition(" ")
        bearer = schema.lower() == "bearer"  # schéma insensible à la casse (RFC 7235)
        brainiac_id = self.server.config.eleve(jeton.strip()) if bearer else None
        if brainiac_id is None:
            self._refuser(HTTPStatus.UNAUTHORIZED, "jeton refusé")
        return brainiac_id

    def _contexte(self, base: Base, brainiac_id: str) -> lectures.Contexte | None:
        eleve = base.brainiac(brainiac_id)
        if eleve is None:  # élève retiré de la base depuis le démarrage
            self._refuser(HTTPStatus.UNAUTHORIZED, "jeton refusé")
            return None
        serveur = self.server
        return lectures.Contexte(serveur.racine, eleve, serveur.horloge(), serveur.dossier_general)

    def _lire(self, brainiac_id: str, lecture: Lecture) -> None:
        try:
            with Base(self.server.racine / "data" / "freinet.db") as base:
                ctx = self._contexte(base, brainiac_id)
                if ctx is None:
                    return
                corps = lecture(base, ctx)
        except lectures.Introuvable as introuvable:
            return self._refuser(HTTPStatus.NOT_FOUND, str(introuvable))
        except (RetourRefuse, ErreurContenu, OSError, ErreurSQLite) as erreur:
            return self._echec("lecture impossible", erreur)
        except Exception as erreur:  # imprévue : un 500 en JSON, jamais une page Python
            return self._echec("erreur interne", erreur)
        self._json(HTTPStatus.OK, corps)

    def _echec(self, motif: str, erreur: Exception) -> None:
        """Un 500 au motif fixe ; le détail va au journal (il ne contient jamais le jeton,
        que les lectures ne voient pas)."""
        sys.stderr.write(f"API ADVIZA, {motif} : {type(erreur).__name__}: {erreur}\n")
        self._refuser(HTTPStatus.INTERNAL_SERVER_ERROR, motif)

    def do_GET(self) -> None:  # noqa: N802
        brainiac_id = self._eleve()
        if brainiac_id is None:
            return
        chemin = urlsplit(self.path).path
        if (trouve := _CONCEPT.match(chemin)) is not None:
            return self._lire(brainiac_id, partial(lectures.concept, concept_id=trouve.group(1)))
        if (trouve := _JOUR.match(chemin)) is not None:
            try:
                jour = date.fromisoformat(trouve.group(1))
            except ValueError:  # 2026-02-30, 0000-01-01
                return self._refuser(HTTPStatus.NOT_FOUND, "jour invalide")
            return self._lire(brainiac_id, partial(lectures.aujourdhui, jour=jour))
        lecture = LECTURES.get(chemin)
        if lecture is None:
            return self._refuser(HTTPStatus.NOT_FOUND, "lecture inconnue")
        self._lire(brainiac_id, lecture)

    def _corps(self) -> object:
        """Le corps JSON, borné avant lecture ; `RequeteRefusee` sinon (rien n'est lu)."""
        valeurs = self.headers.get_all("Content-Length") or []
        if "Transfer-Encoding" in self.headers or not valeurs:
            raise RequeteRefusee(HTTPStatus.LENGTH_REQUIRED, "Content-Length obligatoire")
        if len(valeurs) != 1 or not _LONGUEUR.fullmatch(valeurs[0].strip()):
            raise RequeteRefusee(HTTPStatus.BAD_REQUEST, "Content-Length invalide")
        longueur = int(valeurs[0])
        if longueur > CORPS_MAX:
            raise RequeteRefusee(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "corps trop long")
        try:
            brut = self.rfile.read(longueur)
        except OSError:  # délai dépassé ou connexion coupée pendant la lecture
            raise RequeteRefusee(HTTPStatus.REQUEST_TIMEOUT, "corps incomplet") from None
        if len(brut) != longueur:
            raise RequeteRefusee(HTTPStatus.BAD_REQUEST, "corps incomplet")
        try:
            return json.loads(brut or b"{}")
        except (ValueError, RecursionError):  # JSON ou UTF-8 invalide, imbrication excessive
            raise RequeteRefusee(HTTPStatus.BAD_REQUEST, "JSON invalide") from None

    def do_POST(self) -> None:  # noqa: N802
        brainiac_id = self._eleve()
        if brainiac_id is None:
            return
        trouve = _ACTION.match(urlsplit(self.path).path)
        if trouve is None or trouve.group(1) not in actions.ACTIONS:
            motif = f"action inconnue : {trouve.group(1)}" if trouve else "action inconnue"
            return self._refuser(HTTPStatus.NOT_FOUND, motif)
        cle = self.headers.get("Idempotency-Key", "")
        if not _CLE.fullmatch(cle):
            motif = "en-tête Idempotency-Key absent ou invalide"
            return self._refuser(HTTPStatus.BAD_REQUEST, motif)
        if self.headers.get_content_type() != "application/json":
            return self._refuser(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "JSON attendu")
        try:
            params = self._corps()
            with Base(self.server.racine / "data" / "freinet.db") as base:
                ctx = self._contexte(base, brainiac_id)
                if ctx is None:
                    return
                verrou = self.server.verrou_actions
                resultat = actions.traiter(base, ctx, trouve.group(1), params, cle, verrou)
        except RequeteRefusee as refus:
            return self._refuser(refus.statut, refus.motif)
        except actions.RequeteInvalide as invalide:
            return self._refuser(HTTPStatus.BAD_REQUEST, str(invalide))
        except EnvoiConcurrent as conflit:
            return self._refuser(HTTPStatus.SERVICE_UNAVAILABLE, str(conflit))
        except actions.NonEnregistree as erreur:
            return self._echec("action peut-être appliquée : réessayer", erreur)
        except (ErreurContenu, OSError, ErreurSQLite) as erreur:
            return self._echec("action non enregistrée", erreur)
        except Exception as erreur:  # imprévue : un 500 en JSON, jamais une page Python
            return self._echec("erreur interne", erreur)
        corps = {"contrat": lectures.CONTRAT, **resultat.corps}  # ajouté à l'envoi, pas stocké
        self._json(HTTPStatus(resultat.statut), corps, resultat.rejoue)

    def _methode_refusee(self) -> None:
        if self._eleve() is not None:
            self._refuser(HTTPStatus.METHOD_NOT_ALLOWED, "méthode refusée")

    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _methode_refusee


class ServeurAdviza(ServeurRetour):
    gestionnaire = GestionnaireAdviza

    def __init__(
        self,
        port: int,
        racine: Path,
        config: ConfigAdviza,
        horloge: Callable[[], datetime] = maintenant,
        dossier_general: Path = DOSSIER_GENERAL,
    ) -> None:
        super().__init__((ECOUTE, port), racine, horloge)
        self.config = config
        self.verrou_actions = threading.Lock()  # actions : vérifier, agir, enregistrer d'un bloc
        self.dossier_general = dossier_general


def lancer(
    racine: Path, chemin: Path | None = None, port: int | None = None
) -> ServeurAdviza | None:
    """L'API dans un fil, sur `127.0.0.1` ; `None` sans jeton configuré ; `ValueError` si un
    jeton vise un élève absent de la base."""
    config = lire_config_adviza(chemin)
    if not config.jetons:
        return None
    with Base(racine / "data" / "freinet.db") as base:
        inconnus = sorted(b for b in config.jetons.values() if base.brainiac(b) is None)
    if inconnus:
        raise ValueError(f"_config/adviza.md : élève inconnu {inconnus[0]}")
    instance = ServeurAdviza(config.port if port is None else port, racine, config)
    threading.Thread(target=instance.serve_forever, daemon=True).start()
    return instance
