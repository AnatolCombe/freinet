import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from freinet import adviza_lectures as lectures
from freinet import api_adviza, retour
from freinet.base import Base
from freinet.langue import FR
from freinet.sources import Registre
from freinet.ticket import Bloc, Ticket
from tests.adviza.scenario import (
    JETON_LINA,
    JETON_MARIUS,
    MARDI_MATIN,
    QUETE,
    Site,
    appeler,
    arreter,
    demarrer,
    racine_deux_eleves,
)

LECTURES = ("/adviza/etat", "/adviza/aujourdhui", "/adviza/cartes", "/adviza/catalogue",
            "/adviza/concept/intervalle")  # fmt: skip
ETATS = ("acquis", "en_cours", "debloque", "verrouille")


def _noter_pour_marius(racine: Path, ids: dict[str, str]) -> None:
    with Base(racine / "data" / "freinet.db") as base:
        plan = base.plan_de(ids["marius"], date(2026, 1, 6))
        assert plan is not None
        retour.noter(base, racine, plan, "intervalle-q1", 3, MARDI_MATIN)


def test_etat(site: Site) -> None:
    instance, _, _ = site
    statut, _, corps = appeler(instance, "GET", "/adviza/etat", JETON_MARIUS)
    assert statut == 200 and corps["contrat"] == "1"
    jauges = corps["jauges"]
    ticket = jauges["ticket"]
    assert ticket["jour"] == "2026-01-06" and ticket["notees"] == 0 and ticket["questions"] >= 1
    assert jauges["semaine"] == {"notes": 0, "objectif": 5}
    (carte,) = jauges["maitrise"]
    assert carte["carte"] == "harmonie-demo" and carte["total"] == 4
    assert sum(carte[e] for e in ETATS) == 4
    assert corps["a_faire"][0] == {
        "id": "ticket:2026-01-06",
        "titre": f"Ticket du jour : {ticket['questions']} question(s) à noter",
        "echeance": "2026-01-06",
    }
    profil = corps["profil"]
    assert (profil["nom"], profil["prenom"], profil["langue"]) == ("marius", "MARIUS", "fr")
    assert [(c["id"], c["quete"]) for c in profil["cartes"]] == [("harmonie-demo", QUETE)]


def test_aujourdhui_suit_les_notes(site: Site) -> None:
    instance, racine, ids = site
    _, _, corps = appeler(instance, "GET", "/adviza/aujourdhui", JETON_MARIUS)
    assert (corps["jour"], corps["langue"]) == ("2026-01-06", "fr")
    plan = corps["plan"]
    assert set(plan) == {"statut", "joker", "anecdote", "revisions", "nouvelle", "demain",
                         "defi", "avertissement"}  # fmt: skip
    question = next(r for r in plan["revisions"] if r["question_id"] == "intervalle-q1")
    assert question["note"] is None and question["enonce"] and question["reponse"]
    assert question["concept"] == "Intervalle" and plan["avertissement"] is None
    _noter_pour_marius(racine, ids)
    _, _, apres = appeler(instance, "GET", "/adviza/aujourdhui", JETON_MARIUS)
    notes = {r["question_id"]: r["note"] for r in apres["plan"]["revisions"]}
    assert notes["intervalle-q1"] == 3


def test_cloisonnement_de_toutes_les_lectures(site: Site) -> None:
    instance, racine, ids = site
    _noter_pour_marius(racine, ids)
    notes = {}
    for jeton, soi, autre in ((JETON_MARIUS, "marius", "lina"),
                              (JETON_LINA, "lina", "marius")):  # fmt: skip
        for chemin in LECTURES:
            statut, _, corps = appeler(instance, "GET", chemin, jeton)
            texte = json.dumps(corps, ensure_ascii=False)
            assert statut == 200 and ids[autre] not in texte and ids[soi] not in texte
            assert autre not in texte.lower(), chemin
        _, _, etat = appeler(instance, "GET", f"/adviza/etat?eleve={autre}", jeton)
        assert etat["profil"]["nom"] == soi  # aucun paramètre ne désigne l'élève
        _, _, jour = appeler(instance, "GET", "/adviza/aujourdhui", jeton)
        notes[soi] = [r["note"] for r in jour["plan"]["revisions"] if r["note"] is not None]
    assert notes == {"marius": [3], "lina": []}


def test_sans_ticket_ce_jour(tmp_path: Path) -> None:
    racine = tmp_path / "r"
    instance = demarrer(racine, racine_deux_eleves(racine), datetime(2026, 1, 8, 7, tzinfo=UTC))
    try:
        _, _, etat = appeler(instance, "GET", "/adviza/etat", JETON_MARIUS)
        assert etat["jauges"]["ticket"] is None and etat["jauges"]["notion_du_jour"] is None
        assert etat["a_faire"] == []  # pas de rattrapage (#103)
        _, _, jour = appeler(instance, "GET", "/adviza/aujourdhui", JETON_MARIUS)
        assert jour["plan"] is None and jour["jour"] == "2026-01-08"
    finally:
        arreter(instance)


def test_cartes_et_concept(site: Site) -> None:
    instance, _, _ = site
    _, _, corps = appeler(instance, "GET", "/adviza/cartes", JETON_MARIUS)
    (carte,) = corps["cartes"]
    assert carte["id"] == "harmonie-demo" and carte["quete"]["id"] == QUETE
    assert len(carte["notions"]) == 4 and {n["etat"] for n in carte["notions"]} <= set(ETATS)
    _, _, fiche = appeler(instance, "GET", "/adviza/concept/intervalles", JETON_MARIUS)  # alias
    assert (fiche["id"], fiche["titre"]) == ("intervalle", "Intervalle")
    assert fiche["avertissement"] is None
    assert all(set(s) == {"reference", "titre", "lien"} for s in fiche["sources"])
    for chemin in ("/adviza/concept/inconnu", "/adviza/concept/../etat", "/adviza/concept/A"):
        statut, _, refus = appeler(instance, "GET", chemin, JETON_MARIUS)
        assert statut == 404 and refus["ok"] is False


def test_profil_prive_ne_sort_jamais(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    instance, racine, _ = site
    prive = racine / "brainiacs" / "marius" / "profil" / "essentiel.md"
    prive.parent.mkdir(parents=True, exist_ok=True)
    prive.write_text("---\naccess_tier: prive\n---\nCANARI-PRIVE\n", encoding="utf-8")
    lus: list[Path] = []
    for methode in ("read_text", "read_bytes", "open"):
        origine = getattr(Path, methode)

        def espion(
            chemin: Path, *args: Any, _origine: Callable[..., Any] = origine, **kwargs: Any
        ) -> Any:
            lus.append(chemin)
            return _origine(chemin, *args, **kwargs)

        monkeypatch.setattr(Path, methode, espion)
    for chemin in LECTURES:
        _, _, corps = appeler(instance, "GET", chemin, JETON_MARIUS)
        assert "CANARI-PRIVE" not in json.dumps(corps), chemin  # inv. 11
    assert lus and not [c for c in lus if prive.parent in c.parents]  # jamais ouvert


def test_plan_illisible_sans_fuite(site: Site, capsys: pytest.CaptureFixture[str]) -> None:
    instance, racine, _ = site
    (racine / "brainiacs" / "marius" / "plans" / "2026-01-06.md").unlink()
    for chemin in ("/adviza/etat", "/adviza/aujourdhui"):
        statut, _, corps = appeler(instance, "GET", chemin, JETON_MARIUS)
        assert statut == 500, chemin
        assert corps == {"contrat": "1", "ok": False, "motif": "lecture impossible"}
    assert "2026-01-06.md" in capsys.readouterr().err  # le détail va au journal seulement


def test_fiche_et_cartes_sans_plan_lisible(site: Site) -> None:
    instance, racine, _ = site
    (racine / "brainiacs" / "marius" / "plans" / "2026-01-06.md").write_text("---\n[", "utf-8")
    _, _, fiche = appeler(instance, "GET", "/adviza/concept/intervalle", JETON_MARIUS)
    assert (fiche["langue"], fiche["id"]) == ("fr", "intervalle")  # langue de general.md
    statut, _, corps = appeler(instance, "GET", "/adviza/cartes", JETON_MARIUS)
    assert statut == 200 and corps["langue"] == "fr" and len(corps["cartes"]) == 1


def test_concept_ancre_en_fin_de_chemin() -> None:
    assert api_adviza._CONCEPT.match("/adviza/concept/intervalle") is not None
    assert api_adviza._CONCEPT.match("/adviza/concept/intervalle\n") is None  # `$` l'admettait


def test_notion_du_jour_et_demain(tmp_path: Path) -> None:
    racine = tmp_path / "r"
    instance = demarrer(racine, racine_deux_eleves(racine), datetime(2026, 1, 5, 7, tzinfo=UTC))
    plan = racine / "brainiacs" / "marius" / "plans" / "2026-01-05.md"
    plan.write_text(
        plan.read_text("utf-8").replace("---\n", "---\ndemain: cadence-parfaite\n", 1), "utf-8"
    )
    try:
        _, _, etat = appeler(instance, "GET", "/adviza/etat", JETON_MARIUS)
        assert etat["jauges"]["notion_du_jour"] == {"id": "intervalle", "titre": "Intervalle"}
        (demain,) = [a for a in etat["a_faire"] if a["id"].startswith("demain:")]
        assert demain["id"] == "demain:2026-01-05:cadence-parfaite"
        _, _, jour = appeler(instance, "GET", "/adviza/aujourdhui", JETON_MARIUS)
        assert jour["plan"]["nouvelle"]["id"] == "intervalle"
        assert jour["plan"]["demain"]["id"] == "cadence-parfaite"
        assert jour["plan"]["anecdote"]["source"] == "fr.wikipedia.org"  # l'hôte seul (#45)
    finally:
        arreter(instance)


def test_liens_de_source_selon_le_registre() -> None:
    registre = Registre({"musique": ("imslp.org",), "culture": ("wikipedia.org",)})
    admis = lectures._source("https://imslp.org/wiki/X", "Partition", "musique", registre)
    assert admis == {"reference": "https://imslp.org/wiki/X", "titre": "Partition", "lien": True}
    assert lectures._source("https://exemple.com/x", "", "musique", registre)["lien"] is False
    assert lectures._source("Rameau, Traité (1722)", "", "musique", registre)["lien"] is False


def test_avertissement_finance_repris_du_ticket() -> None:
    blocs = (
        Bloc("titre", FR.anecdote),
        Bloc("texte", "Un fait."),
        Bloc("titre", FR.defi),
        Bloc("texte", "Un défi."),
        Bloc("texte", "suite"),
        Bloc("avertissement", "Éducatif."),
    )
    ticket = Ticket(date(2026, 1, 5), blocs, ())
    assert lectures._extraits(ticket) == ("Un fait.", "Un défi.", "Éducatif.")


def test_a_decouvrir_la_notion_du_jour_seulement(tmp_path: Path) -> None:
    racine = tmp_path / "r"
    ids = racine_deux_eleves(racine)
    attendu = {
        "id": "notion:2026-01-05:intervalle",
        "titre": "À découvrir : Intervalle",
        "echeance": "2026-01-05",
    }
    for quand, decouvrir in ((datetime(2026, 1, 5, 7, tzinfo=UTC), [attendu]),
                             (MARDI_MATIN, []),  # mardi : pas de notion nouvelle
                             (datetime(2026, 1, 8, 7, tzinfo=UTC), [])):  # fmt: skip
        instance = demarrer(racine, ids, quand)
        try:
            _, _, etat = appeler(instance, "GET", "/adviza/etat", JETON_MARIUS)
        finally:
            arreter(instance)
        notions = [a for a in etat["a_faire"] if a["id"].startswith("notion:")]
        assert notions == decouvrir, quand  # ni la veille, ni le lendemain (#103)
        assert (etat["jauges"]["notion_du_jour"] is not None) is bool(decouvrir)
