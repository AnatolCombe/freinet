"""PROF-A4 : `GET /adviza/aujourdhui/<AAAA-MM-JJ>`, le ticket d'un autre jour de la fenêtre
du QR (le jour du ticket à 7 jours après)."""

import json
from datetime import UTC, datetime
from pathlib import Path

from freinet import api_adviza
from tests.adviza.scenario import (
    JETON_LINA,
    JETON_MARIUS,
    Site,
    appeler,
    arreter,
    demarrer,
    racine_deux_eleves,
)

LUNDI = "/adviza/aujourdhui/2026-01-05"
MARDI = "/adviza/aujourdhui/2026-01-06"
NOTER = "/adviza/actions/noter"


def _refus(motif: str) -> dict[str, object]:
    return {"contrat": "1", "ok": False, "motif": motif}


def test_lire_le_ticket_d_un_autre_jour(site: Site) -> None:
    instance, _, _ = site
    _, _, du_jour = appeler(instance, "GET", "/adviza/aujourdhui", JETON_MARIUS)
    statut, _, mardi = appeler(instance, "GET", MARDI, JETON_MARIUS)
    assert statut == 200 and mardi == du_jour  # le jour courant par le chemin : même réponse
    statut, entetes, lundi = appeler(instance, "GET", LUNDI, JETON_MARIUS)
    assert statut == 200 and entetes["Cache-Control"] == "no-store"
    assert set(lundi) == set(du_jour) and set(lundi["plan"]) == set(du_jour["plan"])
    assert (lundi["contrat"], lundi["jour"], lundi["langue"]) == ("1", "2026-01-05", "fr")
    assert lundi["releve_le"] == du_jour["releve_le"]
    plan = lundi["plan"]
    assert plan["revisions"] == [] and plan["nouvelle"]["id"] == "intervalle"
    assert plan["joker"] is False
    corps, cle = {"jour": "2026-01-05"}, {"Idempotency-Key": "joker-lundi"}
    assert appeler(instance, "POST", "/adviza/actions/joker", JETON_MARIUS, corps, cle)[0] == 200
    _, _, apres = appeler(instance, "GET", LUNDI, JETON_MARIUS)
    assert apres["plan"]["joker"] is True  # la lecture suit l'écriture de ce jour-là
    assert appeler(instance, "GET", "/adviza/aujourdhui", JETON_MARIUS)[2] == du_jour
    assert appeler(instance, "GET", LUNDI, JETON_LINA)[2]["plan"]["joker"] is False


def test_refus_a_motif_fixe(site: Site) -> None:
    instance, _, _ = site
    for chemin, motif in (("/adviza/aujourdhui/2026-01-07", "jour hors fenêtre"),  # futur
                          ("/adviza/aujourdhui/2025-12-29", "jour hors fenêtre"),  # J+8
                          ("/adviza/aujourdhui/2025-12-30", "aucun plan ce jour"),  # J+7
                          ("/adviza/aujourdhui/2026-02-30", "jour invalide"),
                          ("/adviza/aujourdhui/0000-01-01", "jour invalide"),
                          ("/adviza/aujourdhui/2026-1-5", "lecture inconnue"),
                          ("/adviza/aujourdhui/20260105", "lecture inconnue"),
                          ("/adviza/aujourdhui/2026-01-05/", "lecture inconnue"),
                          ("/adviza/aujourdhui/2026-01-05%0A", "lecture inconnue"),
                          ("/adviza/aujourdhui/", "lecture inconnue")):  # fmt: skip
        statut, _, corps = appeler(instance, "GET", chemin, JETON_MARIUS)
        assert (statut, corps) == (404, _refus(motif)), chemin


def test_jour_ancre_et_en_chiffres_latins() -> None:
    assert api_adviza._JOUR.match(LUNDI) is not None
    assert api_adviza._JOUR.match(LUNDI + "\n") is None  # `$` l'admettait
    arabes = "٢٠٢٦-٠١-٠٥"  # 2026-01-05 arabe-indien
    assert api_adviza._JOUR.match(f"/adviza/aujourdhui/{arabes}") is None


def test_cloisonnement_et_defenses(site: Site) -> None:
    instance, _, ids = site
    for jeton, soi, autre in ((JETON_MARIUS, "marius", "lina"),
                              (JETON_LINA, "lina", "marius")):  # fmt: skip
        statut, _, corps = appeler(instance, "GET", LUNDI, jeton)
        texte = json.dumps(corps, ensure_ascii=False)
        assert statut == 200 and ids[autre] not in texte and ids[soi] not in texte
        assert autre not in texte.lower()
    assert appeler(instance, "GET", LUNDI)[0] == 401
    for entetes, statut in (({"Origin": "http://evil.example"}, 403),
                            ({"Sec-Fetch-Site": "cross-site"}, 403),
                            ({"Host": "evil.example"}, 421)):  # fmt: skip
        assert appeler(instance, "GET", LUNDI, JETON_MARIUS, entetes=entetes)[0] == statut
    assert appeler(instance, "PUT", LUNDI, JETON_MARIUS)[0] == 405


def test_plan_illisible_500_a_motif_fixe(site: Site) -> None:
    instance, racine, _ = site
    (racine / "brainiacs" / "marius" / "plans" / "2026-01-05.md").unlink()
    statut, _, corps = appeler(instance, "GET", LUNDI, JETON_MARIUS)
    assert (statut, corps) == (500, _refus("lecture impossible"))


def test_lisible_si_et_seulement_si_notable(tmp_path: Path) -> None:
    """Mêmes bornes pour la lecture et pour `noter` (`retour.verifier_delai`)."""
    racine = tmp_path / "r"
    ids = racine_deux_eleves(racine)
    note = {"question_id": "intervalle-q1", "note": 3, "jour": "2026-01-06"}
    for jour, lire, agir, motif in ((5, 404, 422, "pas encore arrivé"),  # la veille
                                    (13, 200, 200, None),  # J+7
                                    (14, 404, 422, "trop ancien pour noter")):  # fmt: skip
        instance = demarrer(racine, ids, datetime(2026, 1, jour, 7, tzinfo=UTC))
        try:
            statut, _, lu = appeler(instance, "GET", MARDI, JETON_MARIUS)
            cle = {"Idempotency-Key": f"noter-{jour}"}
            agi, _, reponse = appeler(instance, "POST", NOTER, JETON_MARIUS, note, cle)
            _, _, relu = appeler(instance, "GET", MARDI, JETON_MARIUS)
        finally:
            arreter(instance)
        assert (statut, agi) == (lire, agir), jour
        if motif is None:
            assert reponse["effet"]["resultat"] == "notée"
            assert [r["note"] for r in relu["plan"]["revisions"]] == [3]  # la note se relit
        else:
            assert lu == _refus("jour hors fenêtre")
            assert reponse["motif"] == f"ticket du 2026-01-06 : {motif}"


def test_a_faire_reste_au_jour_courant(site: Site) -> None:
    instance, _, _ = site
    _, _, avant = appeler(instance, "GET", "/adviza/etat", JETON_MARIUS)
    assert appeler(instance, "GET", LUNDI, JETON_MARIUS)[0] == 200
    _, _, apres = appeler(instance, "GET", "/adviza/etat", JETON_MARIUS)
    assert apres == avant  # une lecture n'écrit rien et ne liste rien (#103, inv. 15)
    assert apres["a_faire"] and all(a["echeance"] == "2026-01-06" for a in apres["a_faire"])
    assert not [a for a in apres["a_faire"] if "2026-01-05" in a["id"]]  # pas de rattrapage
