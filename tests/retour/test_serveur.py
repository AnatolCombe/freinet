import http.client
import re
import socket
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from freinet import api_adviza, serveur
from freinet.base import Base
from freinet.serveur import ENTETES, Limiteur, ServeurRetour
from tests.bibliotheque.demo import surcouche_en
from tests.retour.scenario import LUNDI, passage, racine_demo

MARDI = datetime(2026, 1, 6, 7, tzinfo=UTC)


def _demarrer(racine: Path, quand: datetime) -> ServeurRetour:
    instance = ServeurRetour(("127.0.0.1", 0), racine, lambda: quand, frozenset({"mac.local"}))
    threading.Thread(target=instance.serve_forever, daemon=True).start()
    return instance


def _arreter(instance: ServeurRetour) -> None:
    instance.shutdown()
    instance.server_close()


@pytest.fixture
def site(tmp_path: Path) -> Iterator[tuple[ServeurRetour, Path, str, str]]:
    racine = racine_demo(tmp_path)
    passage(racine, LUNDI)
    acces = passage(racine, LUNDI + timedelta(days=1))
    instance = _demarrer(racine, MARDI)
    try:
        yield instance, racine, acces.jeton, acces.code
    finally:
        _arreter(instance)


def _requete(
    instance: ServeurRetour,
    methode: str,
    chemin: str,
    corps: str = "",
    entetes: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], str]:
    port = instance.server_address[1]
    connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    tout = {"Content-Type": "application/x-www-form-urlencoded"}
    if methode == "POST":
        tout["Origin"] = f"http://127.0.0.1:{port}"  # ce qu'envoie le navigateur
    tout.update(entetes or {})
    connexion.request(methode, chemin, body=corps.encode() if corps else None, headers=tout)
    reponse = connexion.getresponse()
    resultat = reponse.status, dict(reponse.getheaders()), reponse.read().decode("utf-8")
    connexion.close()
    return resultat


def _revues(racine: Path) -> int:
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom("marius")
        assert eleve is not None
        return len(base.revues(eleve.brainiac_id))


def test_la_page_ne_fait_que_lire(site: tuple[ServeurRetour, Path, str, str]) -> None:
    instance, racine, jeton, _ = site
    statut, entetes, corps = _requete(instance, "GET", f"/r/{jeton}")
    assert statut == 200 and "Ticket du 2026-01-06" in corps
    assert "Cette semaine : 0 ticket(s) noté(s) sur 5 visés." in corps
    assert all(entetes[cle] == valeur for cle, valeur in ENTETES.items())
    assert _revues(racine) == 0  # un GET n'écrit jamais


def test_noter_puis_rediriger(site: tuple[ServeurRetour, Path, str, str]) -> None:
    instance, racine, jeton, _ = site
    for _ in range(2):  # double tap : une seule revue
        statut, entetes, _ = _requete(
            instance, "POST", f"/r/{jeton}/note", "question=intervalle-q1&note=3"
        )
        assert statut == 303 and entetes["Location"] == f"/r/{jeton}"
    assert _revues(racine) == 1
    _, _, corps = _requete(instance, "GET", f"/r/{jeton}")
    assert "class=choisie>3 · Bien" in corps


def test_code_court(site: tuple[ServeurRetour, Path, str, str]) -> None:
    instance, racine, _, code = site
    statut, _, corps = _requete(instance, "GET", "/c")
    assert statut == 200 and "Code du ticket" in corps
    statut, entetes, _ = _requete(instance, "GET", f"/c?code={code[:4].lower()}-{code[4:]}")
    assert statut == 303 and entetes["Location"] == f"/k/{code}"
    assert _requete(instance, "POST", f"/k/{code}/note", "question=intervalle-q1&note=2")[0] == 303
    assert _revues(racine) == 1
    assert "Code inconnu" in _requete(instance, "GET", "/c?code=AAAAAAAA")[2]
    assert "Code inconnu" in _requete(instance, "GET", "/c?code=%C3%A9%C3%A9")[2]  # non ASCII


@pytest.mark.parametrize(
    ("methode", "chemin", "corps", "entetes", "attendu"),
    [
        ("GET", "/r/inconnu", "", {}, 404),
        ("GET", "/ailleurs", "", {}, 404),
        ("GET", "/r/JETON/note", "", {}, 404),
        ("GET", "/r/JETON", "", {"Host": "evil.example:8765"}, 421),  # DNS rebinding
        ("GET", "/r/JETON", "", {"Host": "1.2.3.4"}, 421),  # IP publique
        ("POST", "/r/JETON", "", {}, 404),
        ("POST", "/r/JETON/note", "question=intervalle-q1&note=9", {}, 400),
        ("POST", "/r/JETON/note", "question=intervalle-q1&note=%C2%B2", {}, 400),
        ("POST", "/r/JETON/note", "question=autre&note=3", {}, 400),
        ("POST", "/r/JETON/joker", "", {}, 400),  # pas de notion nouvelle ce jour-là
        ("POST", "/r/JETON/note", "x=" + "a" * 2000, {}, 413),
        ("POST", "/r/JETON/note", "note=3", {"Origin": "http://evil.example"}, 403),
        ("POST", "/r/JETON/note", "note=3", {"Origin": ""}, 403),  # POST sans origine
        ("POST", "/r/JETON/note", "note=3", {"Origin": "null"}, 403),
        (
            "POST",
            "/r/JETON/note",
            "note=3",
            {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
            403,
        ),
        (
            "POST",
            "/r/JETON/note",
            "note=3",
            {"Origin": "http://evil.example", "Sec-Fetch-Site": "same-origin"},
            403,
        ),
    ],
)
def test_refus(
    site: tuple[ServeurRetour, Path, str, str],
    methode: str,
    chemin: str,
    corps: str,
    entetes: dict[str, str],
    attendu: int,
) -> None:
    instance, racine, jeton, _ = site
    assert _requete(instance, methode, chemin.replace("JETON", jeton), corps, entetes)[0] == attendu
    assert _revues(racine) == 0


def test_formulaire_tel_que_l_envoie_un_navigateur(
    site: tuple[ServeurRetour, Path, str, str],
) -> None:
    """Chrome envoie `Origin: null` si la page interdit tout référent : la page dit donc
    `same-origin`, et `Sec-Fetch-Site: same-origin` suffit quand l'origine manque."""
    instance, racine, jeton, _ = site
    assert ENTETES["Referrer-Policy"] == "same-origin"
    navigateur = {"Origin": "null", "Sec-Fetch-Site": "same-origin"}
    corps = "question=intervalle-q1&note=4"
    assert _requete(instance, "POST", f"/r/{jeton}/note", corps, navigateur)[0] == 303
    assert _revues(racine) == 1


def test_hotes_admis(site: tuple[ServeurRetour, Path, str, str]) -> None:
    instance, _, jeton, _ = site
    for hote in ("mac.local:8765", "localhost", "192.168.1.20:8765"):
        assert _requete(instance, "GET", f"/r/{jeton}", entetes={"Host": hote})[0] == 200


def test_essais_de_code_limites_par_client(site: tuple[ServeurRetour, Path, str, str]) -> None:
    instance, _, jeton, code = site
    instance.limiteur = Limiteur(par_client=3, en_tout=100, fenetre=60)
    for _ in range(3):
        assert _requete(instance, "GET", "/k/AAAAAAAA")[0] == 404
    statut, _, corps = _requete(instance, "GET", f"/k/{code}")
    assert statut == 429 and "Trop d&#x27;essais" in corps  # le bon code aussi, un temps
    assert _requete(instance, "GET", f"/r/{jeton}")[0] == 200  # le QR n'est jamais limité


def test_limiteur() -> None:
    limiteur = Limiteur(par_client=2, en_tout=3, fenetre=60)
    assert limiteur.autoriser("a") and limiteur.autoriser("a")
    assert not limiteur.autoriser("a")  # plafond du client
    assert limiteur.autoriser("b")
    assert not limiteur.autoriser("c")  # plafond de tous
    oublieux = Limiteur(par_client=1, en_tout=1, fenetre=0.0)
    assert oublieux.autoriser("a") and oublieux.autoriser("a")  # les vieux essais expirent


def test_limiteur_atomique() -> None:
    limiteur = Limiteur(par_client=20, en_tout=20, fenetre=60)
    accordes: list[bool] = []
    fils = [
        threading.Thread(target=lambda: accordes.append(limiteur.autoriser("x")))
        for _ in range(200)
    ]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()
    assert accordes.count(True) == 20


def test_connexion_muette_fermee_apres_le_delai(
    site: tuple[ServeurRetour, Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _, jeton, _ = site
    monkeypatch.setattr(serveur.Gestionnaire, "timeout", 0.5)
    lente = socket.create_connection(("127.0.0.1", instance.server_address[1]), timeout=5)
    lente.sendall(b"GET /r/")  # la requête ne se termine jamais
    debut = time.monotonic()
    assert lente.recv(1024) == b""  # le serveur coupe
    assert time.monotonic() - debut < 4
    lente.close()
    assert _requete(instance, "GET", f"/r/{jeton}")[0] == 200


def test_connexions_simultanees_bornees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(serveur, "CONNEXIONS_MAX", 2)
    racine = racine_demo(tmp_path)
    jeton = passage(racine, LUNDI + timedelta(days=1)).jeton
    instance = _demarrer(racine, MARDI)
    lentes = [
        socket.create_connection(("127.0.0.1", instance.server_address[1]), timeout=5)
        for _ in range(2)
    ]
    try:
        time.sleep(0.2)
        de_trop = socket.create_connection(("127.0.0.1", instance.server_address[1]), timeout=5)
        assert de_trop.recv(1) == b""  # fermée sans être servie
        de_trop.close()
    finally:
        for connexion in lentes:
            connexion.close()
    time.sleep(0.2)
    assert _requete(instance, "GET", f"/r/{jeton}")[0] == 200  # les places se libèrent
    _arreter(instance)


def _coupee(connexion: socket.socket) -> bool:
    try:
        return connexion.recv(1, socket.MSG_DONTWAIT | socket.MSG_PEEK) == b""
    except BlockingIOError:
        return False  # encore ouverte, rien à lire
    except OSError:
        return True


def test_goutte_a_goutte_coupe_a_l_echeance(
    site: tuple[ServeurRetour, Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _, jeton, _ = site
    monkeypatch.setattr(serveur, "DELAI_S", 0.5)  # échéance de la requête entière
    monkeypatch.setattr(serveur.Gestionnaire, "timeout", 5)  # chaque octet arrive à temps
    lente = socket.create_connection(("127.0.0.1", instance.server_address[1]), timeout=5)
    debut = time.monotonic()
    coupee = False
    for _ in range(40):  # un octet toutes les 0,1 s : jamais muet, jamais fini
        try:
            lente.sendall(b"G")
        except OSError:
            coupee = True
            break
        time.sleep(0.1)
        if _coupee(lente):
            coupee = True
            break
    duree = time.monotonic() - debut
    lente.close()
    assert coupee and 0.4 < duree < 3
    assert _requete(instance, "GET", f"/r/{jeton}")[0] == 200


def test_connexions_bornees_par_client(
    site: tuple[ServeurRetour, Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _, jeton, _ = site
    monkeypatch.setattr(serveur, "CONNEXIONS_PAR_CLIENT", 2)
    lentes = [
        socket.create_connection(("127.0.0.1", instance.server_address[1]), timeout=5)
        for _ in range(2)
    ]
    try:
        time.sleep(0.2)
        de_trop = socket.create_connection(("127.0.0.1", instance.server_address[1]), timeout=5)
        assert de_trop.recv(1) == b""
        de_trop.close()
    finally:
        for connexion in lentes:
            connexion.close()
    time.sleep(0.2)
    assert _requete(instance, "GET", f"/r/{jeton}")[0] == 200


def test_client_hors_reseau_prive_refuse(site: tuple[ServeurRetour, Path, str, str]) -> None:
    gestionnaire = serveur.Gestionnaire.__new__(serveur.Gestionnaire)
    for adresse, admis in [
        ("8.8.8.8", False),
        ("100.64.0.1", False),  # Tailscale : V2 (#22)
        ("192.168.1.30", True),
        ("127.0.0.1", True),
    ]:
        gestionnaire.client_address = (adresse, 1234)
        assert gestionnaire._client_admis() is admis


def test_journal_sans_jeton(
    site: tuple[ServeurRetour, Path, str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    instance, _, jeton, _ = site
    _requete(instance, "GET", f"/r/{jeton}")
    assert jeton not in capsys.readouterr().err


def test_acces_expire(tmp_path: Path) -> None:
    racine = racine_demo(tmp_path)
    jeton = passage(racine, LUNDI).jeton
    instance = _demarrer(racine, datetime(2026, 1, 15, 7, tzinfo=UTC))
    try:
        assert _requete(instance, "GET", f"/r/{jeton}")[0] == 404
    finally:
        _arreter(instance)


def test_joker_par_la_page(tmp_path: Path) -> None:
    racine = racine_demo(tmp_path)
    jeton = passage(racine, LUNDI).jeton
    instance = _demarrer(racine, datetime(2026, 1, 5, 7, tzinfo=UTC))
    try:
        assert "Je sais déjà « Intervalle »" in _requete(instance, "GET", f"/r/{jeton}")[2]
        for _ in range(2):  # le joker est idempotent
            assert _requete(instance, "POST", f"/r/{jeton}/joker")[0] == 303
        assert "noté comme déjà su" in _requete(instance, "GET", f"/r/{jeton}")[2]
        (racine / "brainiacs" / "marius" / "plans" / "2026-01-05.md").unlink()
        statut, _, corps = _requete(instance, "GET", f"/r/{jeton}")
        assert statut == 500 and "Page indisponible" in corps
        assert _requete(instance, "POST", f"/r/{jeton}/joker")[0] == 500
    finally:
        _arreter(instance)


def test_commande(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrompre(self: ServeurRetour, poll_interval: float = 0.5) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(ServeurRetour, "serve_forever", interrompre)
    racine = ["--racine", str(tmp_path)]  # jamais les données réelles du dépôt
    assert serveur.main([*racine, "--hote", "127.0.0.1", "--port", "0"]) == 0
    assert "page du QR sur le port" in capsys.readouterr().out
    assert serveur.main([*racine, "--hote", "256.0.0.1", "--port", "0"]) == 1
    assert "page du QR impossible" in capsys.readouterr().err


def test_pages_de_cours_ouvertes(site: tuple[ServeurRetour, Path, str, str]) -> None:
    """Lisibles sans jeton, avec les mêmes défenses ; aucune n'écrit."""
    instance, _, _, _ = site
    for chemin in ["/", "/cours", "/cours/harmonie-demo", "/fiche/cadence-parfaite"]:
        statut, entetes, corps = _requete(instance, "GET", chemin)
        assert statut == 200, chemin
        assert entetes["Content-Security-Policy"] == ENTETES["Content-Security-Policy"]
        assert "<!doctype html>" in corps
    statut, _, corps = _requete(instance, "GET", "/fiche/absente")
    assert statut == 404 and "href='/cours'" in corps
    assert _requete(instance, "POST", "/cours", "x=1")[0] == 404
    assert _requete(instance, "GET", "/cours", entetes={"Host": "ailleurs.example"})[0] == 421


def test_page_du_jour_enrichie(site: tuple[ServeurRetour, Path, str, str]) -> None:
    instance, _, jeton, _ = site
    statut, _, corps = _requete(instance, "GET", f"/r/{jeton}")
    assert statut == 200 and "<summary>Voir la réponse</summary>" in corps
    assert "<summary>Revoir la leçon</summary>" in corps
    assert f"href='/r/{jeton}/fiche/intervalle'" in corps
    assert "Relire la fiche" not in corps
    _requete(instance, "POST", f"/r/{jeton}/note", "question=intervalle-q1&note=1")
    corps = _requete(instance, "GET", f"/r/{jeton}")[2]
    assert "Relire la fiche" in corps  # la démo n'a pas d'explication : repli sur la leçon
    corps = _requete(instance, "GET", f"/r/{jeton}/carte")[2]
    assert f"<a href='/r/{jeton}/cours/harmonie-demo'>Harmonie demo</a>" in corps


def _internes(corps: str) -> list[str]:
    return [h for h in re.findall(r"href='([^']*)'", corps) if not h.startswith("http")]


def test_espace_du_ticket(site: tuple[ServeurRetour, Path, str, str]) -> None:
    """Derrière le jeton : Aujourd'hui, Ma carte, Cours, et aucun lien qui sorte."""
    instance, _, jeton, code = site
    espace = f"/r/{jeton}"
    suites = ["", "/", "/carte", "/cours", "/cours/", "/cours/harmonie-demo", "/fiche/intervalle"]
    for suite in suites:
        statut, _, corps = _requete(instance, "GET", espace + suite)
        assert statut == 200, suite
        assert "<nav class='onglets'>" in corps, suite
        liens = _internes(corps)
        assert liens and all(h == espace or h.startswith(espace + "/") for h in liens), suite
    statut, _, corps = _requete(instance, "GET", espace + "/fiche/absente")
    assert statut == 404 and "<nav class='onglets'>" in corps
    assert _requete(instance, "GET", espace + "/autre")[0] == 404
    assert _requete(instance, "GET", "/r/inconnu/cours")[0] == 404
    statut, _, corps = _requete(instance, "GET", f"/k/{code}/fiche/intervalle")
    assert statut == 200 and f"href='/k/{code}/carte'" in corps
    assert "<nav class='onglets'>" not in _requete(instance, "GET", "/cours")[2]


def test_espace_d_un_ticket_anglais(site: tuple[ServeurRetour, Path, str, str]) -> None:
    instance, racine, jeton, _ = site
    surcouche_en(racine / "bibliotheque")
    chemin = racine / "brainiacs" / "marius" / "plans" / "2026-01-06.md"
    chemin.write_text(
        chemin.read_text(encoding="utf-8").replace("---\n", "---\nlangue: en\n", 1),
        encoding="utf-8",
    )
    statut, _, corps = _requete(instance, "GET", f"/r/{jeton}")
    assert statut == 200 and "<html lang='en'>" in corps and "Morning ticket" in corps
    statut, _, fiche = _requete(instance, "GET", f"/r/{jeton}/fiche/intervalle")
    assert statut == 200 and "<h1>Interval</h1>" in fiche and ">Lessons</a>" in fiche
    statut, _, inconnue = _requete(instance, "GET", f"/r/{jeton}/fiche/absente")
    assert statut == 404 and "Unknown page" in inconnue
    assert "<html lang='fr'>" in _requete(instance, "GET", "/fiche/intervalle")[2]  # public


def test_l_api_ne_bloque_jamais_la_page_du_qr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Fausse:
        arrets = 0
        server_address = ("127.0.0.1", 8766)

        def shutdown(self) -> None:
            Fausse.arrets += 1

        def server_close(self) -> None:
            Fausse.arrets += 1

    def interrompre(self: ServeurRetour, poll_interval: float = 0.5) -> None:
        raise KeyboardInterrupt

    def en_panne(racine: Path) -> None:
        raise OSError("port pris")

    monkeypatch.setattr(ServeurRetour, "serve_forever", interrompre)
    arguments = ["--racine", str(tmp_path), "--hote", "127.0.0.1", "--port", "0"]
    cas: list[tuple[object, str]] = [
        (en_panne, "API ADVIZA arrêtée : port pris"),
        (lambda racine: None, "API ADVIZA : aucun jeton"),
        (lambda racine: Fausse(), "API ADVIZA sur 127.0.0.1:8766"),
    ]
    for lanceur, attendu in cas:
        monkeypatch.setattr(api_adviza, "lancer", lanceur)
        assert serveur.main(arguments) == 0  # la page du QR démarre quoi qu'il arrive
        sorties = capsys.readouterr()
        assert attendu in sorties.out + sorties.err
    assert Fausse.arrets == 2


def test_l_api_adviza_n_est_pas_sur_le_port_du_qr(
    site: tuple[ServeurRetour, Path, str, str],
) -> None:
    instance = site[0]
    bearer = {"Authorization": "Bearer " + "j" * 43}
    for methode, chemin in (("GET", "/adviza/catalogue"), ("POST", "/adviza/actions/noter")):
        statut, entetes, corps = _requete(instance, methode, chemin, "", bearer)
        assert statut == 404 and entetes["Content-Type"] == "text/html; charset=utf-8"
        assert corps.startswith("<!doctype html>") and "Page inconnue" in corps
