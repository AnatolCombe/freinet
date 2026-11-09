import json
import threading
from pathlib import Path

import pytest

from freinet import api_adviza
from freinet.adviza_jetons import ConfigAdviza, empreinte
from freinet.adviza_lectures import Json
from freinet.api_adviza import GestionnaireAdviza, ServeurAdviza, lancer
from tests.adviza.scenario import (
    JETON_LINA,
    JETON_MARIUS,
    MARDI_MATIN,
    QUETE,
    Site,
    appeler,
    arreter,
    racine_deux_eleves,
)
from tests.bibliotheque.demo import surcouche_en
from tests.general.listes import CONFIG_EN, ecrire_general

REFUS_METHODE = {"contrat": "1", "ok": False, "motif": "méthode refusée"}
NAVIGATEUR = {"Origin": "http://evil.example"}


def test_sans_jeton_valide_rien(site: Site) -> None:
    instance, _, _ = site
    for entetes in ({}, {"Authorization": "Bearer faux"}, {"Authorization": JETON_MARIUS}):
        statut, recus, corps = appeler(instance, "GET", "/adviza/catalogue", entetes=entetes)
        assert statut == 401 and recus["WWW-Authenticate"] == "Bearer"
        assert corps == {"contrat": "1", "ok": False, "motif": "jeton refusé"}


def test_catalogue(site: Site) -> None:
    instance, _, _ = site
    statut, entetes, corps = appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)
    assert statut == 200 and entetes["Cache-Control"] == "no-store"
    assert entetes["Content-Type"] == "application/json; charset=utf-8"
    assert corps["contrat"] == "1" and corps["releve_le"] == "2026-01-06T07:00:00+00:00"
    assert corps["langue"] == "fr"
    (carte,) = corps["cartes"]
    assert (carte["id"], carte["concepts"], carte["inscrite"]) == ("harmonie-demo", 4, True)
    assert [q["id"] for q in carte["quetes"]] == [QUETE] and carte["quete_active"] == QUETE


def test_cloisonnement_dans_les_deux_sens(site: Site) -> None:
    instance, _, ids = site
    attendu = {"marius": QUETE, "lina": None}
    for jeton, soi, autre in ((JETON_MARIUS, "marius", "lina"),
                              (JETON_LINA, "lina", "marius")):  # fmt: skip
        for suite in ("", "?eleve=" + autre, "?brainiac_id=" + ids[autre]):
            statut, _, corps = appeler(instance, "GET", "/adviza/catalogue" + suite, jeton)
            assert statut == 200 and corps["cartes"][0]["quete_active"] == attendu[soi]
            texte = json.dumps(corps, ensure_ascii=False)
            assert ids[autre] not in texte and ids[soi] not in texte


def test_defenses(site: Site) -> None:
    instance, _, _ = site
    for entete, statut in (({"Origin": "http://evil.example"}, 403),
                           ({"Sec-Fetch-Site": "cross-site"}, 403),
                           ({"Host": "evil.example"}, 421)):  # fmt: skip
        reponse = appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS, entetes=entete)
        assert reponse[0] == statut and reponse[2]["ok"] is False
    assert appeler(instance, "GET", "/adviza/inconnue", JETON_MARIUS)[0] == 404
    statut, _, corps = appeler(instance, "POST", "/adviza/actions/repondre", JETON_MARIUS, {})
    assert statut == 404 and corps["motif"] == "action inconnue : repondre"  # liste fermée
    assert appeler(instance, "POST", "/r/abc/note", JETON_MARIUS, {})[0] == 404  # jamais le QR
    for methode in ("PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
        statut, entetes, corps = appeler(instance, methode, "/adviza/catalogue", JETON_MARIUS)
        assert statut == 405 and entetes["Allow"] == "GET, POST"
        assert corps == (None if methode == "HEAD" else REFUS_METHODE)
        assert appeler(instance, methode, "/adviza/catalogue")[0] == 401  # défenses d'abord
        refus = appeler(instance, methode, "/adviza/catalogue", JETON_MARIUS, entetes=NAVIGATEUR)
        assert refus[0] == 403
    gestionnaire = GestionnaireAdviza.__new__(GestionnaireAdviza)
    for adresse, admis in (("127.0.0.1", True), ("192.168.1.30", False), ("100.64.0.1", False)):
        gestionnaire.client_address = (adresse, 1234)
        assert gestionnaire._client_de_bouclage() is admis


def test_jeton_jamais_au_journal(site: Site, capsys: pytest.CaptureFixture[str]) -> None:
    instance, _, _ = site
    appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)
    appeler(instance, "GET", "/adviza/catalogue", "faux-" + JETON_LINA)
    journal = capsys.readouterr().err
    assert "GET → 200" in journal and "GET → 401" in journal
    assert JETON_MARIUS not in journal and JETON_LINA not in journal
    assert "Bearer" not in journal


def test_lancer(tmp_path: Path) -> None:
    racine = tmp_path / "r"
    ids = racine_deux_eleves(racine)
    chemin = tmp_path / "adviza.md"
    chemin.write_text("| Port | 8766 |\n", encoding="utf-8")
    assert lancer(racine, chemin) is None  # aucun jeton : pas d'API
    chemin.write_text(f"| 33333333-3333-4333-8333-333333333333 | {empreinte('x')} |\n", "utf-8")
    with pytest.raises(ValueError, match="élève inconnu"):
        lancer(racine, chemin)
    chemin.write_text(f"| {ids['marius']} | {empreinte(JETON_MARIUS)} |\n", encoding="utf-8")
    instance = lancer(racine, chemin, port=0)
    assert instance is not None
    try:
        assert instance.server_address[0] == api_adviza.ECOUTE == "127.0.0.1"
        assert appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)[0] == 200
        assert appeler(instance, "GET", "/adviza/catalogue", JETON_LINA)[0] == 401
    finally:
        arreter(instance)


def test_schema_bearer_sans_casse(site: Site) -> None:
    instance, _, _ = site
    for schema in ("bearer", "BEARER", "BeArEr"):
        entetes = {"Authorization": f"{schema} {JETON_MARIUS}"}
        assert appeler(instance, "GET", "/adviza/catalogue", entetes=entetes)[0] == 200
    assert (
        appeler(instance, "GET", "/adviza/catalogue", entetes={"Authorization": "Basic x"})[0]
        == 401
    )


def test_erreurs_imprevues(
    site: Site, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    instance, _, _ = site

    def imprevue(base: object, ctx: object) -> Json:
        raise KeyError("detail-imprevu")

    def disque(base: object, ctx: object) -> Json:
        raise OSError("detail-disque /chemin/prive")

    for lecture, motif, detail in ((imprevue, "erreur interne", "detail-imprevu"),
                                   (disque, "lecture impossible", "detail-disque")):  # fmt: skip
        monkeypatch.setitem(api_adviza.LECTURES, "/adviza/catalogue", lecture)
        statut, entetes, corps = appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)
        assert statut == 500 and entetes["Content-Type"] == "application/json; charset=utf-8"
        assert corps == {"contrat": "1", "ok": False, "motif": motif}
        journal = capsys.readouterr().err
        assert detail in journal and JETON_MARIUS not in journal


def test_client_hors_bouclage(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    instance, _, _ = site
    monkeypatch.setattr(GestionnaireAdviza, "_client_de_bouclage", lambda self: False)
    statut, _, corps = appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)
    assert statut == 403 and corps["motif"] == "bouclage seulement"


def test_eleve_retire_de_la_base(tmp_path: Path) -> None:
    racine = tmp_path / "r"
    racine_deux_eleves(racine)
    absent = "33333333-3333-4333-8333-333333333333"
    config = ConfigAdviza(8766, {empreinte(JETON_MARIUS): absent})
    instance = ServeurAdviza(0, racine, config, lambda: MARDI_MATIN, ecrire_general(tmp_path / "g"))
    threading.Thread(target=instance.serve_forever, daemon=True).start()
    try:
        statut, _, corps = appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)
        assert statut == 401 and corps["motif"] == "jeton refusé"
    finally:
        arreter(instance)


def test_general_du_scenario_et_illisible(site: Site) -> None:
    instance, racine, _ = site
    surcouche_en(racine / "bibliotheque")
    chemin = instance.dossier_general / "general.md"
    anglais = {**CONFIG_EN, "eleves": {"marius": {"prenom": "MARIUS", "langue": "en"}}}
    ecrire_general(instance.dossier_general, config=anglais)
    assert appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)[2]["langue"] == "en"
    chemin.write_text("---\nni: [yaml\n---\n", encoding="utf-8")  # illisible : on lit quand même
    statut, _, corps = appeler(instance, "GET", "/adviza/catalogue", JETON_MARIUS)
    assert statut == 200 and corps["langue"] == "fr" and corps["cartes"]
