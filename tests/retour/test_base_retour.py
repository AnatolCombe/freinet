from datetime import date, timedelta

import pytest

from freinet.base import Base, ErreurSQLite
from tests.socle.fabrique import revue


def _base_avec_plan() -> tuple[Base, str, str]:
    base = Base(":memory:")
    b = base.ajouter_brainiac("marius", "Europe/Paris")
    return base, b, base.plan_du_jour(b, date(2026, 1, 5), "intervalle")


def test_acces_hache_et_retrouve() -> None:
    base, b, plan = _base_avec_plan()
    with base:
        assert base.acces_du_plan(b, date(2026, 1, 5)) == (None, None)
        base.attribuer_acces(b, date(2026, 1, 5), "h-jeton", "h-code")
        assert base.acces_du_plan(b, date(2026, 1, 5)) == ("h-jeton", "h-code")
        for cle in ("h-jeton", "h-code"):
            trouve = base.plan_par_acces(cle, date(2026, 1, 5))
            assert trouve is not None and (trouve.plan_id, trouve.jour) == (plan, date(2026, 1, 5))
            assert (trouve.nouvelle, trouve.joker) == ("intervalle", False)
        assert base.plan_par_acces("inconnu", date(2026, 1, 1)) is None
        assert base.plan_par_acces("h-jeton", date(2026, 1, 6)) is None  # accès expiré
        with pytest.raises(LookupError, match="aucun plan"):
            base.attribuer_acces(b, date(2026, 1, 6), "x", "y")
        base.plan_du_jour(b, date(2026, 1, 6))
        with pytest.raises(ErreurSQLite):  # un code court n'ouvre qu'un seul plan
            base.attribuer_acces(b, date(2026, 1, 6), "autre", "h-code")


def test_note_joker_et_semaine() -> None:
    base, b, plan = _base_avec_plan()
    with base:
        lundi = date(2026, 1, 5)
        assert base.tickets_notes(b, lundi, lundi + timedelta(days=6)) == 0
        base.marquer_note(plan, joker=True)
        base.marquer_note(plan)  # une note après le joker ne l'efface pas
        assert base.concepts_joker(b, avant=date(2026, 1, 6)) == {"intervalle"}
        assert base.concepts_joker(b, avant=lundi) == set()
        assert base.tickets_notes(b, lundi, lundi + timedelta(days=6)) == 1
        assert base.concepts_presentes(b, avant=date(2026, 1, 6)) == {"intervalle": lundi}
        with pytest.raises(TypeError, match="jour logique"):
            base.tickets_notes(b, lundi, "2026-01-11")  # type: ignore[arg-type]


def test_revue_unique_idempotente() -> None:
    base, b, _ = _base_avec_plan()
    with base:
        r = revue("r1", brainiac_id=b)
        assert base.ajouter_revue_unique(r) is True
        assert base.ajouter_revue_unique(r) is False  # double envoi : rien de plus
        assert [x.revue_id for x in base.revues(b)] == ["r1"]


def test_migration_003() -> None:
    with Base(":memory:") as base:
        assert {"code_hache", "joker"} <= set(base.colonnes("plan_du_jour"))


def test_plan_de_un_eleve() -> None:
    with Base(":memory:") as base:
        marius = base.ajouter_brainiac("marius", "Europe/Paris")
        lina = base.ajouter_brainiac("lina", "Europe/Paris")
        jour = date(2026, 1, 5)
        plan_id = base.plan_du_jour(marius, jour, "intervalle")
        plan = base.plan_de(marius, jour)
        assert plan is not None and (plan.plan_id, plan.nouvelle, plan.joker) == (
            plan_id, "intervalle", False,
        )  # fmt: skip
        assert base.plan_de(lina, jour) is None  # cloisonné
        assert base.plan_de(marius, jour + timedelta(days=1)) is None
