import json
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from freinet import adviza_actions, api_adviza, retour
from freinet.base import Base, ErreurSQLite
from tests.adviza.scenario import (
    JETON_LINA,
    JETON_MARIUS,
    QUETE,
    Reponse,
    Site,
    appeler,
    arreter,
    demarrer,
    racine_deux_eleves,
)  # fmt: skip

NOTER = "/adviza/actions/noter"
Q1 = {"question_id": "intervalle-q1", "note": 3}


def _agir(site: Site, chemin: str, jeton: str, corps: object, cle: str) -> Reponse:
    return appeler(site[0], "POST", chemin, jeton, corps, {"Idempotency-Key": cle})


def _revues(racine: Path, brainiac_id: str) -> list[tuple[str, int, str]]:
    with Base(racine / "data" / "freinet.db") as base:
        return [(r.question_id, r.note, r.canal) for r in base.revues(brainiac_id)]


def _brut(
    site: Site,
    entetes: dict[str, str],
    corps: bytes = b"",
    doubles: tuple[tuple[str, str], ...] = (),
    fermer: bool = True,
) -> Reponse:
    """Un POST sur `noter` aux en-têtes exacts (`doubles` : répétés), écrit sur le socket puis,
    si `fermer`, fermé en écriture : ni `Content-Length` ajouté d'office, ni attente d'un
    corps annoncé plus long."""
    tout = {"Host": "127.0.0.1", "Authorization": f"Bearer {JETON_MARIUS}"}
    tout |= {"Idempotency-Key": "brut", "Content-Type": "application/json"} | entetes
    paires = [*tout.items(), *doubles]
    lignes = [f"POST {NOTER} HTTP/1.1", *(f"{c}: {v}" for c, v in paires), "", ""]
    with socket.create_connection(("127.0.0.1", site[0].server_address[1]), timeout=5) as s:
        s.sendall("\r\n".join(lignes).encode("latin-1") + corps)
        if fermer:
            s.shutdown(socket.SHUT_WR)
        recu = b"".join(iter(lambda: s.recv(65536), b""))
    tete, _, donnees = recu.partition(b"\r\n\r\n")
    premiere, *reste = tete.decode("latin-1").split("\r\n")
    recus = dict(ligne.split(": ", 1) for ligne in reste)
    return int(premiere.split()[1]), recus, json.loads(donnees)


def test_une_cle_ne_s_execute_qu_une_fois(site: Site) -> None:
    _, racine, ids = site
    premier = _agir(site, NOTER, JETON_MARIUS, Q1, "carte-1:1")
    effet = {"jour": "2026-01-06", "question_id": "intervalle-q1", "note": 3, "resultat": "notée"}
    assert premier[0] == 200 and premier[2] == {"contrat": "1", "ok": True, "effet": effet}
    assert "Idempotent-Replayed" not in premier[1]
    rejoue = _agir(site, NOTER, JETON_MARIUS, Q1, "carte-1:1")
    assert rejoue[0] == 200 and rejoue[2] == premier[2]
    assert rejoue[1]["Idempotent-Replayed"] == "true"
    assert _revues(racine, ids["marius"]) == [("intervalle-q1", 3, "adviza")]
    autre = _agir(site, NOTER, JETON_MARIUS, Q1 | {"note": 2}, "carte-1:1")
    assert autre[0] == 409 and autre[2]["ok"] is False  # même clé, autre requête
    assert autre[2]["contrat"] == "1"
    ordre = _agir(
        site, NOTER, JETON_MARIUS, {"note": 3, "question_id": "intervalle-q1"}, "carte-1:1"
    )
    assert ordre[0] == 200 and ordre[1]["Idempotent-Replayed"] == "true"  # mêmes clés JSON
    joker = _agir(site, "/adviza/actions/joker", JETON_MARIUS, {}, "carte-1:1")
    assert joker[0] == 409  # même clé, autre action
    corrige = _agir(site, NOTER, JETON_MARIUS, Q1 | {"note": 2}, "carte-1:2")
    assert corrige[2]["effet"]["resultat"] == "corrigée"


def test_cle_rejouee_en_meme_temps(site: Site) -> None:
    _, racine, ids = site
    with ThreadPoolExecutor(4) as fils:  # 4 connexions par client au plus (`serveur`)
        reponses = list(fils.map(lambda _: _agir(site, NOTER, JETON_MARIUS, Q1, "k:1"), range(8)))
    assert {r[0] for r in reponses} == {200}
    assert sum("Idempotent-Replayed" not in r[1] for r in reponses) == 1
    assert _revues(racine, ids["marius"]) == [("intervalle-q1", 3, "adviza")]


def test_un_refus_metier_est_rejoue_tel_quel(site: Site) -> None:
    absente = {"question_id": "absente-q9", "note": 3}
    for rejoue in (False, True):
        statut, entetes, corps = _agir(site, NOTER, JETON_MARIUS, absente, "carte-2:1")
        assert statut == 422 and corps["ok"] is False and corps["contrat"] == "1"
        assert corps["motif"] == "cette question n'est pas sur ce ticket"
        assert ("Idempotent-Replayed" in entetes) is rejoue
    statut, _, corps = _agir(site, NOTER, JETON_MARIUS, Q1 | {"jour": "2026-01-09"}, "carte-3:1")
    assert statut == 422 and corps["motif"] == "aucun ticket le 2026-01-09"
    statut, _, corps = _agir(site, NOTER, JETON_MARIUS, Q1 | {"note": 7}, "carte-3:2")
    assert statut == 422 and corps["motif"] == "note invalide (1 à 4)"


def test_joker(tmp_path: Path) -> None:
    racine = tmp_path / "r"
    ids = racine_deux_eleves(racine)
    lundi = datetime(2026, 1, 5, 7, tzinfo=UTC)  # le ticket de lundi a une notion nouvelle
    instance = demarrer(racine, ids, lundi)
    site = (instance, racine, ids)
    try:
        for _ in range(2):
            statut, _, corps = _agir(site, "/adviza/actions/joker", JETON_MARIUS, {}, "joker-1")
            assert statut == 200 and corps["effet"] == {"jour": "2026-01-05", "joker": True}
        with Base(racine / "data" / "freinet.db") as base:
            du_jour = {n: base.plan_de(ids[n], date(2026, 1, 5)) for n in ("marius", "lina")}
        assert [p is not None and p.joker for p in du_jour.values()] == [True, False]
    finally:
        arreter(instance)


def test_choisir_carte(site: Site) -> None:
    _, racine, ids = site
    choix = {"carte_id": "harmonie-demo", "quete_id": QUETE}
    statut, _, corps = _agir(site, "/adviza/actions/choisir_carte", JETON_LINA, choix, "c-1")
    assert statut == 200 and corps["effet"] == choix
    with Base(racine / "data" / "freinet.db") as base:
        inscrites = [(i.carte_id, i.quete_active) for i in base.inscriptions(ids["lina"])]
    assert inscrites == [("harmonie-demo", QUETE)]
    sans_quete = {"carte_id": "harmonie-demo"}
    for params in (sans_quete, sans_quete | {"quete_id": None}):  # `null` = absent
        statut, entetes, _ = _agir(site, "/adviza/actions/choisir_carte", JETON_LINA, params, "c-4")
        assert statut == 200
    assert entetes["Idempotent-Replayed"] == "true"
    for cle, params, motif in (("c-2", {"carte_id": "inconnue"}, "carte inconnue : inconnue"),
                               ("c-3", {"carte_id": "harmonie-demo", "quete_id": "x"},
                                "quête inconnue : x")):  # fmt: skip
        statut, _, corps = _agir(site, "/adviza/actions/choisir_carte", JETON_LINA, params, cle)
        assert statut == 422 and corps["motif"] == motif


def test_chaque_eleve_n_agit_que_sur_lui(site: Site) -> None:
    instance, racine, ids = site
    _, _, jour = appeler(instance, "GET", "/adviza/aujourdhui", JETON_LINA)
    question = jour["plan"]["revisions"][0]["question_id"]
    meme_cle = "carte-commune:1"
    assert _agir(site, NOTER, JETON_MARIUS, Q1 | {"note": 4}, meme_cle)[0] == 200
    sienne = {"question_id": question, "note": 1}
    lina = _agir(site, NOTER, JETON_LINA, sienne, meme_cle)
    assert lina[0] == 200 and "Idempotent-Replayed" not in lina[1]  # pas de 409 croisé
    rejoue = _agir(site, NOTER, JETON_MARIUS, Q1 | {"note": 4}, meme_cle)
    assert rejoue[1]["Idempotent-Replayed"] == "true" and rejoue[2]["effet"]["note"] == 4
    assert _revues(racine, ids["marius"]) == [("intervalle-q1", 4, "adviza")]
    assert _revues(racine, ids["lina"]) == [(question, 1, "adviza")]
    for jeton in (JETON_LINA, JETON_MARIUS):
        for intrus in ({"eleve": "marius"}, {"brainiac_id": ids["lina"]}):
            for chemin, params in ((NOTER, Q1), ("/adviza/actions/joker", {}),
                                   ("/adviza/actions/choisir_carte",
                                    {"carte_id": "harmonie-demo"})):  # fmt: skip
                statut, _, _ = _agir(site, chemin, jeton, params | intrus, "carte-x:1")
                assert statut == 400  # aucun paramètre ne désigne l'élève


def test_requetes_mal_formees_ne_consomment_pas_la_cle(site: Site) -> None:
    instance, racine, ids = site
    cas: list[tuple[dict[str, str], object, str, int]] = [
        ({}, Q1, NOTER, 400),  # sans clé
        ({"Idempotency-Key": "a b"}, Q1, NOTER, 400),
        ({"Idempotency-Key": "k"}, [1], NOTER, 400),
        ({"Idempotency-Key": "k"}, Q1 | {"note": "3"}, NOTER, 400),
        ({"Idempotency-Key": "k"}, Q1 | {"note": True}, NOTER, 400),
        ({"Idempotency-Key": "k"}, Q1 | {"jour": "demain"}, NOTER, 400),
        ({"Idempotency-Key": "k"}, {"note": 3}, NOTER, 400),
        ({"Idempotency-Key": "k"}, {"question_id": "x" * 129, "note": 3}, NOTER, 400),
        ({"Idempotency-Key": "k"}, {"question_id": "x" * 5000, "note": 3}, NOTER, 413),
        ({"Idempotency-Key": "k"}, {}, "/adviza/actions/repondre", 404),
        ({"Idempotency-Key": "k"}, {}, "/adviza/actions/Noter!", 404),
        ({"Idempotency-Key": "k", "Content-Type": "text/plain"}, None, NOTER, 415),
    ]
    for entetes, corps, chemin, attendu in cas:
        statut, _, reponse = appeler(instance, "POST", chemin, JETON_MARIUS, corps, entetes)
        assert statut == attendu and reponse["ok"] is False, (chemin, corps)
    assert _revues(racine, ids["marius"]) == []
    assert _agir(site, NOTER, JETON_MARIUS, Q1, "k")[0] == 200  # la clé était restée libre


def test_corps_borne_avant_lecture(site: Site) -> None:
    _, racine, ids = site
    texte = json.dumps(Q1).encode()
    cas: list[tuple[dict[str, str], bytes, int, str]] = [
        ({}, b"", 411, "Content-Length obligatoire"),
        ({"Transfer-Encoding": "chunked"}, b"0\r\n\r\n", 411, "Content-Length obligatoire"),
        ({"Content-Length": "abc"}, b"", 400, "Content-Length invalide"),
        ({"Content-Length": "2"}, b"{}", 400, "Content-Length invalide"),  # répété (doubles)
        ({"Content-Length": "-1"}, b"", 400, "Content-Length invalide"),
        ({"Content-Length": str(api_adviza.CORPS_MAX + 1)}, b"", 413, "corps trop long"),
        ({"Content-Length": "9"}, b"{invalide", 400, "JSON invalide"),
        ({"Content-Length": "2"}, b"\xff\xfe", 400, "JSON invalide"),
        ({"Content-Length": "3000"}, b"[" * 3000, 400, "JSON invalide"),  # trop imbriqué
        ({"Content-Length": str(len(texte) + 5)}, texte, 400, "corps incomplet"),
    ]
    for entetes, corps, attendu, motif in cas:
        doubles = (("Content-Length", "2"),) if corps == b"{}" else ()
        statut, recus, reponse = _brut(site, entetes, corps, doubles)
        assert (statut, reponse["motif"]) == (attendu, motif), entetes
        assert recus["Content-Type"] == "application/json; charset=utf-8"
    assert _revues(racine, ids["marius"]) == []
    assert _brut(site, {"Content-Length": str(len(texte))}, texte)[0] == 200


def test_une_panne_laisse_la_cle_libre(
    site: Site, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def en_panne(*_: object, **__: object) -> str:
        raise OSError("disque plein /chemin/prive")

    def imprevue(*_: object, **__: object) -> str:
        raise KeyError("detail-imprevu")

    for panne, motif, detail in ((en_panne, "action non enregistrée", "disque plein"),
                                 (imprevue, "erreur interne", "detail-imprevu")):  # fmt: skip
        monkeypatch.setattr(adviza_actions, "noter", panne)
        statut, _, corps = _agir(site, NOTER, JETON_MARIUS, Q1, "carte-4:1")
        assert statut == 500 and corps == {"contrat": "1", "ok": False, "motif": motif}
        journal = capsys.readouterr().err
        assert detail in journal and JETON_MARIUS not in journal
    monkeypatch.undo()  # `retour.noter` revient
    assert _agir(site, NOTER, JETON_MARIUS, Q1, "carte-4:1")[2]["effet"]["resultat"] == "notée"


def test_post_sans_jeton_ni_bouclage(site: Site) -> None:
    instance, _, _ = site
    assert appeler(instance, "POST", NOTER, None, Q1, {"Idempotency-Key": "k"})[0] == 401
    navigateur = {"Idempotency-Key": "k", "Origin": "http://evil.example"}
    assert appeler(instance, "POST", NOTER, JETON_MARIUS, Q1, navigateur)[0] == 403


def test_corps_qui_n_arrive_pas(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_adviza.GestionnaireAdviza, "timeout", 0.2)
    statut, _, corps = _brut(site, {"Content-Length": "20"}, b"{", fermer=False)
    assert (statut, corps["motif"]) == (408, "corps incomplet")


def test_conflit_passager_laisse_la_cle_libre(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    def conflit(*_: object, **__: object) -> str:
        raise retour.EnvoiConcurrent("trop d'envois simultanés : réessayer")

    monkeypatch.setattr(adviza_actions, "noter", conflit)
    statut, entetes, corps = _agir(site, NOTER, JETON_MARIUS, Q1, "carte-5:1")
    assert statut == 503 and entetes["Retry-After"] == "1"
    assert corps == {"contrat": "1", "ok": False, "motif": "trop d'envois simultanés : réessayer"}
    monkeypatch.undo()
    reponse = _agir(site, NOTER, JETON_MARIUS, Q1, "carte-5:1")
    assert reponse[0] == 200 and reponse[2]["effet"]["resultat"] == "notée"


def test_enregistrement_en_panne_apres_l_action(
    site: Site, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, racine, ids = site

    def en_panne(*_: object, **__: object) -> bool:
        raise ErreurSQLite("base verrouillée")

    monkeypatch.setattr(Base, "enregistrer_requete_adviza", en_panne)
    statut, _, corps = _agir(site, NOTER, JETON_MARIUS, Q1, "carte-6:1")
    assert statut == 500 and corps["motif"] == "action peut-être appliquée : réessayer"
    assert "base verrouillée" in capsys.readouterr().err
    monkeypatch.undo()
    reponse = _agir(site, NOTER, JETON_MARIUS, Q1, "carte-6:1")
    assert reponse[0] == 200 and reponse[2]["effet"]["resultat"] == "inchangée"
    assert _revues(racine, ids["marius"]) == [("intervalle-q1", 3, "adviza")]


def test_cle_prise_entre_lecture_et_enregistrement(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un autre processus enregistre la clé pendant l'action : sa réponse fait foi."""
    _, racine, ids = site
    with Base(racine / "data" / "freinet.db") as base:
        effet = {"jour": "2026-01-06", "question_id": "intervalle-q1", "note": 3, "resultat": "x"}
        premiere = {"statut": 200, "corps": {"ok": True, "effet": effet}}
        signature = adviza_actions._empreinte("noter", Q1)
        base.enregistrer_requete_adviza(ids["marius"], "k:7", "noter", signature,
                                        json.dumps(premiere))  # fmt: skip
    vraie, appels = Base.requete_adviza, []

    def aveugle_une_fois(self: Base, brainiac_id: str, cle: str) -> tuple[str, str, str] | None:
        appels.append(cle)
        return None if len(appels) == 1 else vraie(self, brainiac_id, cle)

    monkeypatch.setattr(Base, "requete_adviza", aveugle_une_fois)
    statut, entetes, corps = _agir(site, NOTER, JETON_MARIUS, Q1, "k:7")
    assert statut == 200 and entetes["Idempotent-Replayed"] == "true"
    assert corps["effet"]["resultat"] == "x" and len(appels) == 2
