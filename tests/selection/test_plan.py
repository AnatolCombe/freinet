from dataclasses import replace
from pathlib import Path

from freinet.frontmatter import lire
from freinet.langue import EN, FR
from freinet.plan import ecrire_plan, phrase_par_defaut, plan_markdown
from freinet.selection import Item, Serendipite, selectionner
from tests.selection.scenario import BIB, DOSE, INSCRIPTION, LUNDI, reponse, selection


def _relire(tmp_path: Path, texte: str) -> tuple[dict[str, object], str]:
    """Relit le plan comme le fera la page QR (#16)."""
    chemin = tmp_path / "plan.md"
    chemin.write_text(texte, encoding="utf-8")
    return lire(chemin)


def test_plan_du_premier_jour(tmp_path: Path) -> None:
    s = selection([])
    assert s.anecdote is not None
    entete, corps = _relire(tmp_path, plan_markdown(s, BIB, phrase_par_defaut(s)))
    assert entete == {
        "type": "plan",
        "jour": "2026-01-05",
        "brainiac_id": "b1",
        "graine": "2026-01-05:b1",
        "reprise": False,
        "nouvelle": "intervalle",
        "items": [],
        "anecdote": {"concept_id": "cadence-parfaite", "source": s.anecdote.source},
    }
    assert f"> {FR.phrase_defaut}" in corps
    assert f"## Anecdote du café\n\n{s.anecdote.texte}" in corps
    assert "## Nouveau · Intervalle" in corps and "## Révisions" not in corps
    assert "Cadence parfaite ~ Intervalle (analogie)" in corps
    assert (
        f"## Défi du jour\n\n{FR.defis[s.jour.toordinal() % len(FR.defis)]}".format(
            titre="Intervalle"
        )
        in corps
    )
    assert "## Quête\n\nReconnaître une cadence parfaite à l'oreille : 0/4" in corps


def test_plan_avec_revisions_et_reprise(tmp_path: Path) -> None:
    s = selection([reponse(1, "intervalle-q1", 4, 0), reponse(2, "intervalle-q2", 1, 1)], 5)
    chemin = ecrire_plan(s, BIB, tmp_path / "marius", phrase_par_defaut(s))
    assert chemin == tmp_path / "marius" / "plans" / "2026-01-10.md"
    assert [p.name for p in chemin.parent.iterdir()] == ["2026-01-10.md"]  # pas de temporaire
    entete, corps = lire(chemin)
    assert entete["reprise"] is True and entete["nouvelle"] is None
    assert entete["items"] == [
        {"question_id": "intervalle-q1", "concept_id": "intervalle", "nature": "rappel"}
    ]
    assert f"> {FR.phrase_reprise}" in corps and "On reprend ici" in corps
    assert "## Révisions\n\n1. " in corps  # neutre : « au stylo » relève du ticket (B4)


def test_pre_test_note_en_dernier_et_pose_avant_la_lecon(tmp_path: Path) -> None:
    pre_test = replace(BIB.questions["intervalle-q1"], id="intervalle-q9", nature="pre_test")
    bib = replace(BIB, questions={**BIB.questions, pre_test.id: pre_test})
    s = selectionner(bib, [], [], INSCRIPTION, "b1", "Europe/Paris", (0, 100, 0), DOSE, LUNDI)
    rappel = Item("cadence-parfaite", "cadence-parfaite-q1", "rappel", "Une cadence ?")
    s = replace(s, revisions=(rappel,))  # une révision due le même jour que le pré-test
    entete, corps = _relire(tmp_path, plan_markdown(s, bib, "Allez."))
    assert entete["items"] == [
        {
            "question_id": "cadence-parfaite-q1",
            "concept_id": "cadence-parfaite",
            "nature": "rappel",
        },
        {"question_id": "intervalle-q9", "concept_id": "intervalle", "nature": "pre_test"},
    ]
    assert f"Avant de lire : {pre_test.enonce}\n\n" in corps
    assert "> Allez." in corps  # la phrase du coach remplace celle par défaut (inv. 7)


def test_le_premier_plan_ecrit_gagne(tmp_path: Path) -> None:
    s = selection([])
    chemin = ecrire_plan(s, BIB, tmp_path, "Premier.")
    assert ecrire_plan(s, BIB, tmp_path, "Second.") == chemin
    assert "> Premier." in chemin.read_text(encoding="utf-8")
    assert [p.name for p in chemin.parent.iterdir()] == [chemin.name]  # pas de temporaire


def test_textes_sur_plusieurs_lignes_ne_cassent_pas_le_plan(tmp_path: Path) -> None:
    s = selection([reponse(1, "intervalle-q1", 1, 0)], 1)
    piege = "\n\n## Faux titre\n---\n"
    revision = replace(s.revisions[0], enonce=f"Question ?{piege}")
    s = replace(
        s,
        revisions=(revision,),
        serendipite=Serendipite("inconnu", "intervalle", "analogie"),
    )
    entete, corps = _relire(tmp_path, plan_markdown(s, BIB, f"Courage.{piege}"))
    assert entete["type"] == "plan"
    assert "\n## Faux titre" not in corps and "\n---" not in corps
    assert "> Courage. ## Faux titre ---" in corps
    assert "inconnu ~ Intervalle (analogie)" in corps  # concept absent : l'id, pas d'erreur


def test_plan_en_anglais(tmp_path: Path) -> None:
    s = selection([reponse(1, "intervalle-q1", 1, 0)], 1, libelles=EN)
    texte = plan_markdown(s, BIB, phrase_par_defaut(s, EN), langue="en")
    entete, corps = _relire(tmp_path, texte)
    assert entete["langue"] == "en"
    assert f"> {EN.phrase_defaut}" in corps
    assert "## Review\n" in corps and "## Today's challenge" in corps
    assert "Révisions" not in corps and "Défi du jour" not in corps


def test_plan_francais_sans_cle_de_langue(tmp_path: Path) -> None:
    s = selection([])
    entete, _ = _relire(tmp_path, plan_markdown(s, BIB, phrase_par_defaut(s)))
    assert "langue" not in entete
