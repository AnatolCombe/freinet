"""`quotidien/04_retour` : la page du QR, servie en local (#16).

`python -m freinet.serveur` écoute sur le réseau local. Une page sans JavaScript :
- `GET /r/<jeton>` (le QR) ou `GET /k/<code>` (le code court) ouvre l'espace du ticket
  (`espace.py`) : Aujourd'hui (le ticket à noter), `…/carte` (Ma carte), `…/cours…` et
  `…/fiche/<concept>` (la bibliothèque, sans quitter l'espace) ;
- `POST …/note` et `POST …/joker` écrivent, puis redirigent (seul un POST écrit) ;
- `GET /c` : saisir le code court à la main ;
- `GET /cours`, `/cours/<carte>`, `/fiche/<concept>` : les pages de lecture (`pages.py`),
  ouvertes sans jeton, mêmes défenses ; elles ne montrent que la bibliothèque.
Défenses :
- client hors réseau privé refusé ; en-tête Host limité au nom du QR, à `localhost` ou à une
  adresse IP (contre le « DNS rebinding ») ; POST sans Origin, ou d'une autre origine, refusé ;
- corps borné, 10 s par lecture et par requête, connexions bornées (32, dont 4 par client) ;
- essais du code court limités par client (le jeton de 128 bits n'en a pas besoin) ;
- accès expirés au-delà de la fenêtre de notation ; en-têtes stricts (pas de cache, pas de
  référent : le jeton est dans l'adresse) ; journal sans l'adresse.
L'espace d'un ticket suit la langue de son plan (PROF-12) ; les pages ouvertes et les messages
d'erreur restent en français.
`--racine` désigne les données ; `_config/retour.md` est celui du dépôt.
Le même processus sert l'API d'ADVIZA sur 127.0.0.1 (`api_adviza.py`, PROF-A) ; sa panne
n'arrête pas le QR.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import ipaddress
import re
import socket
import sys
import threading
import time
from collections import Counter, deque
from collections.abc import Callable
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from freinet import pages
from freinet.acces import cle_acces, hacher, lire_config_retour, normaliser_code
from freinet.base import Base, ErreurSQLite
from freinet.base.plans import PlanAcces
from freinet.bibliotheque import charger
from freinet.espace import page_de_lecture, page_du_jour, page_ma_carte
from freinet.frontmatter import ErreurContenu
from freinet.libelles_espace import libelles_espace
from freinet.pages import document
from freinet.retour import JOURS_VALIDES, RetourRefuse, joker, langue_du_ticket, noter, page
from freinet.sources import lire_registre
from freinet.temps import maintenant

RACINE = Path(__file__).resolve().parent.parent
CORPS_MAX = 1024
ESSAIS_PAR_CLIENT, ESSAIS_EN_TOUT, FENETRE_S = 10, 60, 600.0
DELAI_S = 10.0  # par lecture du socket, et pour la requête entière
CONNEXIONS_MAX = 32
CONNEXIONS_PAR_CLIENT = 4
_CHEMIN = re.compile(r"^/(r|k)/([A-Za-z0-9_-]{1,64})(/[a-z0-9/-]*)?$")
ENTETES = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
    # « same-origin » et non « no-referrer » : avec no-referrer, le navigateur envoie
    # `Origin: null` sur un POST de formulaire et aucune note ne passerait. Le jeton ne part
    # ainsi que vers la page elle-même.
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class Limiteur:
    """Essais de code court : au plus `par_client` par client et `en_tout` pour tous, par
    fenêtre de `fenetre` secondes. Vérifier et compter se font sous le même verrou."""

    def __init__(
        self,
        par_client: int = ESSAIS_PAR_CLIENT,
        en_tout: int = ESSAIS_EN_TOUT,
        fenetre: float = FENETRE_S,
    ) -> None:
        self.par_client, self.en_tout, self.fenetre = par_client, en_tout, fenetre
        self._essais: deque[tuple[float, str]] = deque()
        self._verrou = threading.Lock()

    def autoriser(self, client: str) -> bool:
        with self._verrou:
            instant = time.monotonic()
            while self._essais and self._essais[0][0] <= instant - self.fenetre:
                self._essais.popleft()
            du_client = sum(1 for _, qui in self._essais if qui == client)
            if du_client >= self.par_client or len(self._essais) >= self.en_tout:
                return False
            self._essais.append((instant, client))
            return True


class Gestionnaire(BaseHTTPRequestHandler):
    server: ServeurRetour
    server_version = "FREINET"
    sys_version = ""
    timeout = DELAI_S  # appliqué au socket : une connexion muette ne garde pas un fil

    def setup(self) -> None:
        super().setup()
        # Échéance de la requête entière : un client au goutte-à-goutte (1 octet toutes les
        # 9 s) ne garde pas sa place indéfiniment.
        self._echeance = threading.Timer(DELAI_S, self._couper)
        self._echeance.daemon = True
        self._echeance.start()

    def _couper(self) -> None:
        with contextlib.suppress(OSError):
            self.connection.shutdown(socket.SHUT_RDWR)

    def finish(self) -> None:
        self._echeance.cancel()
        with contextlib.suppress(OSError):
            super().finish()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Jamais l'adresse : elle contient le jeton.
        sys.stderr.write(f"{self.command} → {args[1] if len(args) > 1 else ''}\n")

    def _repondre(self, statut: HTTPStatus, corps: bytes = b"", lieu: str | None = None) -> None:
        self.send_response(statut)
        for cle, valeur in ENTETES.items():
            self.send_header(cle, valeur)
        if lieu:
            self.send_header("Location", lieu)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _refus(self, statut: HTTPStatus, message: str) -> None:
        self._repondre(statut, document(message, f"<p>{html.escape(message)}</p>"))

    def _client_admis(self) -> bool:
        adresse = ipaddress.ip_address(self.client_address[0])
        return adresse.is_private or adresse.is_loopback

    def _hote_admis(self) -> bool:
        hote = urlsplit(f"//{self.headers.get('Host', '')}").hostname or ""
        try:
            adresse = ipaddress.ip_address(hote)
        except ValueError:
            return hote in self.server.hotes
        return adresse.is_private or adresse.is_loopback

    def _admis(self) -> bool:
        if not self._client_admis():
            self._refus(HTTPStatus.FORBIDDEN, "Réseau local seulement.")
            return False
        if not self._hote_admis():
            self._refus(HTTPStatus.MISDIRECTED_REQUEST, "Adresse inattendue.")
            return False
        return True

    def _plan(self, genre: str, secret: str) -> PlanAcces | None:
        """Le plan de ce jeton ou de ce code ; `LookupError` si le code est trop essayé."""
        if genre == "k" and not self.server.limiteur.autoriser(self.client_address[0]):
            raise LookupError("trop d'essais de code : réessayer dans dix minutes")
        secret = secret if genre == "r" else normaliser_code(secret)
        depuis = self.server.horloge().date() - timedelta(days=JOURS_VALIDES + 1)
        with Base(self.server.racine / "data" / "freinet.db") as base:
            return base.plan_par_acces(hacher(self.server.cle, secret), depuis)

    def do_GET(self) -> None:  # noqa: N802
        if not self._admis():
            return
        morceaux = urlsplit(self.path)
        if pages.est_page_de_cours(morceaux.path):
            return self._cours(morceaux.path)
        if morceaux.path == "/c":
            return self._saisie_code(parse_qs(morceaux.query).get("code", [""])[0])
        trouve = _CHEMIN.match(morceaux.path)
        suite = (trouve.group(3) or "").rstrip("/") if trouve else ""
        if trouve is None or not (suite in ("", "/carte") or pages.est_page_de_cours(suite)):
            return self._refus(HTTPStatus.NOT_FOUND, "Page inconnue.")
        self._afficher(trouve.group(1), trouve.group(2), suite)

    def _cours(self, chemin: str) -> None:
        try:
            titre, corps = pages.page_de_cours(
                chemin, charger(self.server.racine / "bibliotheque"), lire_registre()
            )
        except pages.PageInconnue:
            corps = "<p>Page inconnue.</p><p><a href='/cours'>Tous les cours</a></p>"
            return self._repondre(HTTPStatus.NOT_FOUND, document("Page inconnue", corps))
        except (ErreurContenu, OSError) as erreur:
            return self._refus(HTTPStatus.INTERNAL_SERVER_ERROR, f"Page indisponible : {erreur}")
        self._repondre(HTTPStatus.OK, document(titre, corps))

    def _saisie_code(self, code: str) -> None:
        erreur = ""
        if code:
            code = normaliser_code(code)
            try:
                if self._plan("k", code) is not None:
                    return self._repondre(HTTPStatus.SEE_OTHER, lieu=f"/k/{code}")
            except LookupError as trop:
                return self._refus(HTTPStatus.TOO_MANY_REQUESTS, str(trop).capitalize() + ".")
            erreur = "<p class='aide'>Code inconnu.</p>"
        formulaire = (
            f"{erreur}<form class='code' method='get' action='/c'><label>Code du ticket "
            "<input name='code' autocomplete='off' autocapitalize='characters'></label>"
            "<button>Ouvrir</button></form>"
        )
        self._repondre(HTTPStatus.OK, document("Code du ticket", formulaire))

    def _afficher(self, genre: str, secret: str, suite: str) -> None:
        try:
            plan = self._plan(genre, secret)
        except LookupError as trop:
            return self._refus(HTTPStatus.TOO_MANY_REQUESTS, str(trop).capitalize() + ".")
        if plan is None:
            return self._refus(HTTPStatus.NOT_FOUND, "Ticket inconnu.")
        espace = f"/{genre}/{secret}"
        web = libelles_espace("fr")
        try:
            with Base(self.server.racine / "data" / "freinet.db") as base:
                langue = langue_du_ticket(base, self.server.racine, plan)
            web = libelles_espace(langue)
            bib = charger(self.server.racine / "bibliotheque", langue)
            if suite in ("", "/carte"):
                with Base(self.server.racine / "data" / "freinet.db") as base:
                    contenu = page(base, bib, self.server.racine, plan, langue)
                faire = page_ma_carte if suite else page_du_jour
                rendu = faire(contenu, espace, web)
            else:
                titre, corps = pages.page_de_cours(suite, bib, lire_registre(), espace, web)
                rendu = page_de_lecture(titre, corps, espace, web)
        except pages.PageInconnue:
            vide = f"<p class='vide'>{web.page_inconnue}.</p>"
            inconnue = page_de_lecture(web.page_inconnue, vide, espace, web)
            return self._repondre(HTTPStatus.NOT_FOUND, inconnue)
        except (RetourRefuse, ErreurContenu, OSError, ErreurSQLite) as erreur:
            return self._refus(HTTPStatus.INTERNAL_SERVER_ERROR, f"Page indisponible : {erreur}")
        self._repondre(HTTPStatus.OK, rendu)

    def do_POST(self) -> None:  # noqa: N802
        if not self._admis():
            return
        origine = self.headers.get("Origin", "")
        if origine in ("", "null"):  # sans origine : l'indication du navigateur fait foi
            meme_origine = self.headers.get("Sec-Fetch-Site") == "same-origin"
        else:
            meme_origine = urlsplit(origine).netloc == self.headers.get("Host")
        if not meme_origine:
            return self._refus(HTTPStatus.FORBIDDEN, "Origine refusée.")
        trouve = _CHEMIN.match(self.path)
        if trouve is None or trouve.group(3) not in ("/note", "/joker"):
            return self._refus(HTTPStatus.NOT_FOUND, "Page inconnue.")
        try:
            longueur = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            longueur = -1
        if not 0 <= longueur <= CORPS_MAX:
            return self._refus(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Requête refusée.")
        champs = parse_qs(self.rfile.read(longueur).decode("utf-8", "replace"), max_num_fields=4)
        genre, secret, action = trouve.groups()
        try:
            plan = self._plan(genre, secret)
        except LookupError as trop:
            return self._refus(HTTPStatus.TOO_MANY_REQUESTS, str(trop).capitalize() + ".")
        if plan is None:
            return self._refus(HTTPStatus.NOT_FOUND, "Ticket inconnu.")
        try:
            with Base(self.server.racine / "data" / "freinet.db") as base:
                if action == "/joker":
                    joker(base, self.server.racine, plan, self.server.horloge())
                else:
                    note = champs.get("note", [""])[0]
                    question = champs.get("question", [""])[0]
                    if note not in {"1", "2", "3", "4"}:
                        raise RetourRefuse("note invalide (1 à 4)")
                    noter(
                        base, self.server.racine, plan, question, int(note), self.server.horloge()
                    )
        except RetourRefuse as erreur:
            return self._refus(HTTPStatus.BAD_REQUEST, str(erreur))
        except (ErreurContenu, OSError, ErreurSQLite) as erreur:
            return self._refus(HTTPStatus.INTERNAL_SERVER_ERROR, f"Note non enregistrée : {erreur}")
        self._repondre(HTTPStatus.SEE_OTHER, lieu=f"/{genre}/{secret}")


class ServeurRetour(ThreadingHTTPServer):
    daemon_threads = True
    gestionnaire: type[Gestionnaire] = Gestionnaire  # l'API ADVIZA a le sien (PROF-A)

    def __init__(
        self,
        adresse: tuple[str, int],
        racine: Path,
        horloge: Callable[[], datetime] = maintenant,
        hotes: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(adresse, self.gestionnaire)
        self.racine = racine
        self.horloge = horloge
        self.hotes = hotes | {"localhost"}
        self.cle = cle_acces(racine)
        self.limiteur = Limiteur()
        self._verrou = threading.Lock()
        self._ouvertes: Counter[str] = Counter()

    def process_request(self, request: Any, client_address: Any) -> None:
        """Au plus `CONNEXIONS_MAX` connexions, dont `CONNEXIONS_PAR_CLIENT` par client :
        au-delà, la connexion est fermée sans être servie."""
        client = str(client_address[0])
        with self._verrou:
            plein = sum(self._ouvertes.values()) >= CONNEXIONS_MAX
            if plein or self._ouvertes[client] >= CONNEXIONS_PAR_CLIENT:
                self.shutdown_request(request)
                return
            self._ouvertes[client] += 1
        super().process_request(request, client_address)

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._verrou:
                self._ouvertes[str(client_address[0])] -= 1


def _lancer_api(racine: Path) -> ServeurRetour | None:
    """L'API d'ADVIZA à côté de la page du QR ; sa panne n'arrête jamais le QR (CC)."""
    from freinet import api_adviza  # ici : `api_adviza` importe ce module

    try:
        api = api_adviza.lancer(racine)
    except (ValueError, OSError, ErreurSQLite) as erreur:
        print(f"API ADVIZA arrêtée : {erreur}", file=sys.stderr)
        return None
    if api is None:
        print("API ADVIZA : aucun jeton (_config/adviza.md)", flush=True)
    else:
        print(f"API ADVIZA sur 127.0.0.1:{api.server_address[1]}", flush=True)
    return api


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__)
    lecteur.add_argument("--racine", type=Path, default=RACINE)
    lecteur.add_argument("--hote", help="adresse d'écoute (défaut : _config/retour.md)")
    lecteur.add_argument("--port", type=int, help="port (défaut : _config/retour.md)")
    options = lecteur.parse_args(arguments)
    try:
        config = lire_config_retour()
        adresse = (
            options.hote or config.ecoute,
            config.port if options.port is None else options.port,
        )
        hote_qr = urlsplit(config.adresse).hostname or ""
        serveur = ServeurRetour(adresse, options.racine, hotes=frozenset({hote_qr}))
    except (ValueError, OSError) as erreur:
        print(f"page du QR impossible : {erreur}", file=sys.stderr)
        return 1
    print(f"page du QR sur le port {serveur.server_address[1]}", flush=True)
    api = _lancer_api(options.racine)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
        if api is not None:
            api.shutdown()
            api.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
