from dataclasses import replace
from datetime import date, timedelta

import pytest

from freinet.bibliotheque import Bibliotheque
from freinet.contenu import Lateral
from freinet.langue import EN, FR
from freinet.modele import Inscription, Revue
from freinet.rejeu import rejouer
from freinet.selection import Item, Selection, Serendipite, selectionner
from tests.selection.scenario import BIB, DOSE, INSCRIPTION, LUNDI, REGLES, reponse, selection


def test_premier_jour() -> None:
    s = selection([])
    assert (s.jour, s.reprise, s.revisions) == (date(2026, 1, 5), False, ())
    assert s.nouvelle is not None and s.nouvelle.concept_id == "intervalle"
    assert s.serendipite == Serendipite("cadence-parfaite", "intervalle", "analogie")
    assert s.anecdote is not None and s.anecdote.concept_id == "cadence-parfaite"
    assert s.defi == FR.defis[date(2026, 1, 5).toordinal() % len(FR.defis)].format(
        titre="Intervalle"
    )
    assert s.quete is not None and (s.quete.acquis, s.quete.total) == (0, 4)


def test_reproductible_meme_graine_meme_etat() -> None:
    revues = [reponse(1, "intervalle-q1", 1, 0)]
    assert selection(revues, 1, (60, 25, 15)) == selection(revues, 1, (60, 25, 15))
    assert selection(revues, 1).graine == "2026-01-06:b1"


def _carte_a_plat() -> Bibliotheque:
    """Quatre concepts sans prérequis ; intervalle ~ septième par un lien latéral."""
    carte = replace(
        BIB.cartes["harmonie-demo"],
        prerequis=(),
        lateraux=(Lateral("intervalle", "septieme-de-dominante", "analogie"),),
    )
    return replace(BIB, cartes={carte.id: carte})


@pytest.mark.parametrize(
    ("jour", "dosage", "attendu"),
    [
        (0, (0, 100, 0), "accord-parfait"),  # déclarés : le premier débloqué
        (0, (0, 0, 100), "septieme-de-dominante"),  # sérendipité : le voisin d'une notion déjà vue
        (5, (0, 100, 0), "septieme-de-dominante"),  # samedi : 100 % sérendipité (A2)
        (0, (-5, 100, 0), "accord-parfait"),  # un poids négatif compte pour zéro
    ],
)
def test_origine_de_la_notion_nouvelle(
    jour: int, dosage: tuple[int, int, int], attendu: str
) -> None:
    bib = _carte_a_plat()
    s = selectionner(
        bib,
        [],
        [],
        INSCRIPTION,
        "b1",
        "Europe/Paris",
        dosage,
        DOSE,
        LUNDI + timedelta(days=jour),
        {"intervalle": date(2026, 1, 4) + timedelta(days=jour)},
    )
    assert s.nouvelle is not None and s.nouvelle.concept_id == attendu


def test_week_end_et_dosage_nul_gardent_une_notion() -> None:
    assert selection([], 5, (100, 0, 0)).nouvelle is not None
    assert selection([], 0, (0, 0, 0)).nouvelle is not None


def test_notion_presentee_jamais_notee_passe_en_premier_rappel() -> None:
    s = selectionner(
        BIB,
        [],
        [],
        INSCRIPTION,
        "b1",
        "Europe/Paris",
        (0, 100, 0),
        DOSE,
        LUNDI + timedelta(days=1),
        {"intervalle": date(2026, 1, 5)},
    )
    assert [i.question_id for i in s.revisions] == ["intervalle-q1"]
    assert s.nouvelle is None or s.nouvelle.concept_id != "intervalle"


def test_eleve_qui_ne_scanne_jamais_passe_en_reprise() -> None:
    def sans_scan(jour: int) -> Selection:
        return selectionner(
            BIB,
            [],
            [],
            INSCRIPTION,
            "b1",
            "Europe/Paris",
            (0, 100, 0),
            DOSE,
            LUNDI + timedelta(days=jour),
            {"intervalle": date(2026, 1, 5)},
        )

    assert not sans_scan(2).reprise
    s = sans_scan(3)
    assert s.reprise and s.nouvelle is None


def test_notion_renommee_reste_presentee() -> None:
    renomme = replace(BIB.concepts["intervalle"], alias=("intervalles",))
    bib = replace(BIB, concepts={**BIB.concepts, renomme.id: renomme})
    s = selectionner(
        bib,
        [],
        [],
        INSCRIPTION,
        "b1",
        "Europe/Paris",
        (0, 100, 0),
        DOSE,
        LUNDI + timedelta(days=1),
        {"intervalles": date(2026, 1, 5)},  # présentée sous son ancien identifiant (#20)
    )
    assert [i.question_id for i in s.revisions] == ["intervalle-q1"]
    assert s.nouvelle is None or s.nouvelle.concept_id != "intervalle"


def test_concept_rate_revient_avec_une_autre_question() -> None:
    s = selection([reponse(1, "intervalle-q1", 1, 0)], 1)
    assert [i.question_id for i in s.revisions] == ["intervalle-q2"]


def test_question_non_notee_reste_due_sans_penalite() -> None:
    revues = [reponse(1, "intervalle-q1", 1, 0)]
    assert selection(revues, 1).revisions == selection(revues, 2).revisions  # inv. 15


def test_dose_plafonne_les_revisions_les_plus_fragiles_d_abord() -> None:
    revues = [
        reponse(n, f"{c}-q1", 1, 0)
        for n, c in enumerate(
            ["accord-parfait", "cadence-parfaite", "intervalle", "septieme-de-dominante"]
        )
    ]
    s = selection(revues, 1)
    assert len(s.revisions) == DOSE.revisions == 3  # inv. 14
    assert [i.concept_id for i in s.revisions] == [
        "accord-parfait",
        "cadence-parfaite",
        "intervalle",
    ]


def test_deblocage_apres_acquisition() -> None:
    revues = [
        reponse(1, "intervalle-q1", 3, 0),
        reponse(2, "intervalle-q3", 3, 2),
        reponse(3, "intervalle-q2", 3, 13),
    ]
    s = selection(revues, 14)
    assert s.nouvelle is not None and s.nouvelle.concept_id == "accord-parfait"
    assert s.quete is not None and s.quete.acquis == 1


# Dernier scan le mardi 6 ; `intervalle` est dû le mercredi 7 et reste sans réponse.
EN_ATTENTE = [reponse(1, "intervalle-q1", 4, 0), reponse(2, "intervalle-q2", 1, 1)]


def test_reprise_comptee_en_jours_logiques() -> None:
    veille_matin, veille_soir = selection(EN_ATTENTE, 4), selection(EN_ATTENTE, 4.7)  # ven. 9
    assert not veille_matin.reprise and veille_matin == veille_soir
    matin, soir = selection(EN_ATTENTE, 5), selection(EN_ATTENTE, 5.7)  # sam. 10, 6 h et 23 h
    assert matin.reprise and matin == soir


def test_reussite_corrigee_n_est_plus_une_reussite() -> None:
    revues = [reponse(1, "intervalle-q1", 4, 0), reponse(2, "intervalle-q2", 1, 0)]
    correction = replace(reponse(3, "intervalle-q1", 1, 0), corrige_id="r001")
    s = selection([*revues, correction], 4)
    assert s.reprise and s.fil_ariane is not None and "dernière réussite" not in s.fil_ariane


def test_scan_d_une_seule_correction_compte_comme_un_retour() -> None:
    correction = replace(reponse(3, "intervalle-q1", 1, 5), corrige_id="r001")
    assert selection(EN_ATTENTE, 6).reprise
    assert not selection([*EN_ATTENTE, correction], 6).reprise


def test_eleve_a_jour_jamais_en_reprise() -> None:
    """Rien d'échu = rien à scanner : pas de reprise, et une nouvelle carte donne sa notion."""
    revues: list[Revue] = []
    presentes: dict[str, date] = {}
    for jour in range(20):
        s = selectionner(
            BIB,
            rejouer(revues, REGLES, BIB.canonique),
            revues,
            INSCRIPTION,
            "b1",
            "Europe/Paris",
            (0, 100, 0),
            DOSE,
            LUNDI + timedelta(days=jour),
            presentes,
        )
        assert not s.reprise, jour
        if s.nouvelle:
            presentes.setdefault(s.nouvelle.concept_id, s.jour)
        for item in s.revisions:  # tout est noté 4 le jour même
            revues.append(reponse(len(revues) + 1, item.question_id, 4, jour + 0.1))
    solo = replace(
        BIB.cartes["harmonie-demo"],
        id="solo",
        concepts=("accord-parfait",),
        prerequis=(),
        lateraux=(),
        quetes=(),
    )
    bib = replace(BIB, cartes={**BIB.cartes, solo.id: solo})
    lendemain = selectionner(
        bib,
        rejouer(revues, REGLES, bib.canonique),
        revues,
        [*INSCRIPTION, Inscription("solo", None)],
        "b1",
        "Europe/Paris",
        (0, 100, 0),
        DOSE,
        LUNDI + timedelta(days=20),
    )
    assert not lendemain.reprise and lendemain.nouvelle is not None


def test_reprise_apres_trois_jours() -> None:
    s = selection(EN_ATTENTE, 5)
    assert s.reprise and s.nouvelle is None
    assert s.revisions == (
        Item("intervalle", "intervalle-q1", "rappel", BIB.questions["intervalle-q1"].enonce),
    )
    assert s.fil_ariane == (
        "On reprend ici — quête « Reconnaître une cadence parfaite à l'oreille », 0/4 ;"
        " dernière réussite : « Intervalle »."
    )


def test_pre_test_avant_la_notion() -> None:
    pre_test = replace(BIB.questions["intervalle-q1"], id="intervalle-q9", nature="pre_test")
    bib = replace(BIB, questions={**BIB.questions, pre_test.id: pre_test})
    s = selectionner(
        bib,
        [],
        [],
        [Inscription("harmonie-demo", None)],
        "b1",
        "Europe/Paris",
        (0, 100, 0),
        DOSE,
        LUNDI,
    )
    assert s.nouvelle is not None and s.nouvelle.pre_test is not None
    assert s.nouvelle.pre_test.question_id == "intervalle-q9"
    assert s.quete is None


def test_sans_inscription_rien_a_faire() -> None:
    s = selectionner(BIB, [], [], [], "b1", "Europe/Paris", (0, 100, 0), DOSE, LUNDI)
    assert (s.nouvelle, s.serendipite, s.anecdote, s.defi, s.quete) == (
        None,
        None,
        None,
        None,
        None,
    )


def test_renommage_regroupe_le_journal() -> None:
    revues = [reponse(1, "intervalle-q1", 1, 0)]
    revues = [replace(revues[0], concept_id="intervalles")]  # ancien id, gardé en alias
    s = selection(revues, 1)
    assert [i.concept_id for i in s.revisions] == ["intervalle"]


def test_defi_et_fil_d_ariane_en_anglais() -> None:
    s = selection([], libelles=EN)
    assert s.defi == EN.defis[date(2026, 1, 5).toordinal() % len(EN.defis)].format(
        titre="Intervalle"
    )
