import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from freinet import eleves, quotidien
from freinet.base import Base
from freinet.frontmatter import lire
from freinet.temps import depuis_iso
from tests.bibliotheque.demo import DEMO, surcouche_en
from tests.general.listes import CONFIG_EN, ecrire_general
from tests.selection.scenario import reponse

LUNDI = "2026-01-05T05:00:00+00:00"


def _racine(tmp_path: Path, inscrire: bool = True) -> Path:
    shutil.copytree(DEMO, tmp_path / "bibliotheque")
    assert eleves.main(["--racine", str(tmp_path), "ajouter", "marius", "Europe/Paris"]) == 0
    if inscrire:
        arguments = ["--racine", str(tmp_path), "inscrire", "marius", "harmonie-demo"]
        assert eleves.main([*arguments, "--quete", "entendre-une-cadence"]) == 0
    return tmp_path


def _passage(racine: Path, instant: str = LUNDI) -> int:
    return quotidien.main(["--racine", str(racine), "--eleve", "marius", "--instant", instant])


def _plan(racine: Path, jour: str = "2026-01-05") -> Path:
    return racine / "brainiacs" / "marius" / "plans" / f"{jour}.md"


def _base(racine: Path) -> Base:
    return Base(racine / "data" / "freinet.db")


def _brainiac_id(base: Base) -> str:
    eleve = base.brainiac_par_nom("marius")
    assert eleve is not None
    return eleve.brainiac_id


def _imprime(racine: Path, jour: date = date(2026, 1, 5)) -> None:
    with _base(racine) as base:
        base.marquer_imprime(_brainiac_id(base), jour)


def _presentes(racine: Path) -> dict[str, date]:
    with _base(racine) as base:
        return base.concepts_presentes(_brainiac_id(base), avant=date(2026, 1, 6))


def test_passage_du_matin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = _racine(tmp_path)
    assert _passage(racine) == 0
    assert str(_plan(racine)) in capsys.readouterr().out
    entete, corps = lire(_plan(racine))
    assert entete["nouvelle"] == "intervalle"
    assert "## Quête\n\nReconnaître une cadence parfaite à l'oreille : 0/4" in corps
    assert _presentes(racine) == {}  # présentée seulement une fois le ticket imprimé
    _imprime(racine)
    assert _presentes(racine) == {"intervalle": date(2026, 1, 5)}


def test_plan_ecrit_est_fige(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    assert _passage(racine) == 0
    premier = _plan(racine).read_text(encoding="utf-8")
    with _base(racine) as base:
        scan = replace(reponse(1, "intervalle-q1", 1, 0.1), brainiac_id=_brainiac_id(base))
        base.ajouter_revue(scan)
    assert _passage(racine) == 0  # un scan entre deux passages ne change pas le ticket
    assert _plan(racine).read_text(encoding="utf-8") == premier
    retouche = premier.replace("Un pas de plus", "Un grand pas")
    _plan(racine).write_text(retouche, encoding="utf-8")
    assert _passage(racine) == 0  # la retouche à la main est conservée
    assert _plan(racine).read_text(encoding="utf-8") == retouche


def test_la_base_suit_le_fichier_du_plan(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    assert _passage(racine) == 0
    _imprime(racine)
    # Base restaurée d'avant le passage : le plan écrit réserve de nouveau sa notion.
    with _base(racine) as base:
        base.fixer_plan(_brainiac_id(base), date(2026, 1, 5), None)
    assert _presentes(racine) == {}
    assert _passage(racine) == 0
    assert _presentes(racine) == {"intervalle": date(2026, 1, 5)}
    # Notion retirée à la main du plan : la base l'oublie aussi.
    texte = _plan(racine).read_text(encoding="utf-8")
    _plan(racine).write_text(texte.replace("nouvelle: intervalle", "nouvelle: null"), "utf-8")
    assert _passage(racine) == 0
    assert _presentes(racine) == {}


def test_notion_non_notee_ne_revient_pas_comme_nouvelle(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    assert _passage(racine) == 0
    _imprime(racine)
    assert _passage(racine, "2026-01-06T05:00:00+00:00") == 0
    entete, _ = lire(_plan(racine, "2026-01-06"))
    assert entete["nouvelle"] != "intervalle"  # pas deux fois la même leçon
    assert {"question_id": "intervalle-q1", "concept_id": "intervalle", "nature": "rappel"} in (
        entete["items"]  # type: ignore[operator]
    )  # premier rappel, sans avoir scanné


def test_ticket_jamais_imprime_la_notion_revient(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    assert _passage(racine) == 0  # imprimante éteinte : rien n'est marqué imprimé
    assert _passage(racine, "2026-01-06T05:00:00+00:00") == 0
    entete, _ = lire(_plan(racine, "2026-01-06"))
    assert entete["nouvelle"] == "intervalle" and entete["items"] == []


@pytest.mark.parametrize(
    ("inscrire", "eleve", "message"),
    [
        (True, "personne", "élève inconnu"),
        (False, "marius", "aucune carte inscrite"),
    ],
)
def test_rien_a_preparer(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    inscrire: bool,
    eleve: str,
    message: str,
) -> None:
    racine = _racine(tmp_path, inscrire)
    arguments = ["--racine", str(racine), "--eleve", eleve, "--instant", LUNDI]
    assert quotidien.main(arguments) == 1
    erreur = capsys.readouterr().err
    assert message in erreur
    assert not (racine / "brainiacs").exists()  # aucun plan vide figé pour la journée


def test_plan_fige_sans_relire_la_bibliotheque(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    assert _passage(racine) == 0
    shutil.rmtree(racine / "bibliotheque")  # ex. pendant une publication : la réimpression marche
    assert _passage(racine) == 0


def test_bibliotheque_cassee_une_ligne_d_erreur(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = _racine(tmp_path)
    (racine / "bibliotheque" / "concepts" / "intervalle.md").write_text("pas de frontmatter")
    assert _passage(racine) == 1
    assert "passage du matin impossible" in capsys.readouterr().err


@pytest.mark.parametrize("instant", ["2026-01-05T05:00:00", "demain"])
def test_instant_sans_fuseau_est_une_erreur_d_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], instant: str
) -> None:
    with pytest.raises(SystemExit) as sortie:
        _passage(tmp_path, instant)
    assert sortie.value.code == 2
    assert "instant ISO 8601 avec fuseau attendu" in capsys.readouterr().err


def _deuxieme_carte(racine: Path) -> None:
    (racine / "bibliotheque" / "cartes" / "mini.md").write_text(
        "---\ntype: carte\nid: mini\nconcepts: [intervalle]\nprerequis: []\nlateraux: []\n"
        "quetes: []\n---\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["ajouter", "ami", "Mars/Olympus"], "fuseau inconnu"),
        (["ajouter", "../evasion", "Europe/Paris"], "nom invalide"),
        (["ajouter", "marius", "Europe/Paris"], "élève déjà existant"),
        (["inscrire", "personne", "harmonie-demo"], "élève inconnu"),
        (["inscrire", "marius", "carte-absente"], "carte inconnue"),
        (["inscrire", "marius", "harmonie-demo", "--quete", "absente"], "quête inconnue"),
        (["inscrire", "marius", "mini", "--quete", "entendre-une-cadence"], "appartient"),
    ],
)
def test_eleves_refus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], arguments: list[str], message: str
) -> None:
    racine = _racine(tmp_path, inscrire=False)
    _deuxieme_carte(racine)
    assert eleves.main(["--racine", str(racine), *arguments]) == 1
    erreur = capsys.readouterr().err
    assert message in erreur
    with _base(racine) as base:
        assert base.brainiacs() == [_brainiac_id(base)]  # rien d'écrit
        assert base.inscriptions(_brainiac_id(base)) == []


def test_nom_invalide_ne_cree_pas_la_base(tmp_path: Path) -> None:
    assert eleves.main(["--racine", str(tmp_path), "ajouter", "Bad Name", "Europe/Paris"]) == 1
    assert not (tmp_path / "data").exists()


def test_partie_generale_dans_le_plan(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    assert _passage(racine) == 0
    entete, corps = lire(_plan(racine))
    assert entete["prenom"] == "MARIUS"
    general = entete["general"]
    assert isinstance(general, dict) and set(general) == {"mot", "fait", "enigme", "meteo"}
    assert general["meteo"] is False  # tests sans réseau (conftest)
    assert "## Mot du jour · " in corps and "[cadre : 5]" in corps
    assert "## Météo" not in corps and "## Un mot de" not in corps


def test_meme_partie_generale_pour_deux_eleves(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    assert eleves.main(["--racine", str(racine), "ajouter", "noor", "Europe/Paris"]) == 0
    assert eleves.main(["--racine", str(racine), "inscrire", "noor", "harmonie-demo"]) == 0
    # Profils figés dans le test, pas lus dans `_config/general/` (exemple neutre du dépôt).
    dossier = ecrire_general(tmp_path / "general", en=True)
    for nom in ("marius", "noor"):
        quotidien.preparer_jour(racine, nom, depuis_iso(LUNDI), False, dossier)
    lui, _ = lire(_plan(racine))
    elle, corps = lire(racine / "brainiacs" / "noor" / "plans" / "2026-01-05.md")
    assert lui["general"] == elle["general"]
    assert (lui["prenom"], elle["prenom"]) == ("MARIUS", "NOOR")
    assert "## A word from Marius\n\n[écrire : 2]" in corps  # noor lit l'anglais (A13)


def test_partie_generale_invalide_le_ticket_sort_quand_meme(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Décision B (Marius, 2026-09-30) : une liste générale cassée ne bloque pas le ticket."""
    racine = _racine(tmp_path)
    dossier = ecrire_general(tmp_path / "general", mots=[])
    quotidien.preparer_jour(racine, "marius", depuis_iso(LUNDI), False, dossier)
    entete, corps = lire(_plan(racine))
    assert "general" not in entete and "## Mot du jour" not in corps  # sans partie générale
    assert "## Quête" in corps  # la partie apprentissage sort
    erreur = capsys.readouterr().err
    assert "partie générale absente" in erreur and "aucun mot pour" in erreur


def _noor(tmp_path: Path) -> Path:
    racine = _racine(tmp_path)
    assert eleves.main(["--racine", str(racine), "ajouter", "noor", "Europe/Paris"]) == 0
    assert eleves.main(["--racine", str(racine), "inscrire", "noor", "harmonie-demo"]) == 0
    return racine


def test_plan_d_un_eleve_anglophone(tmp_path: Path) -> None:
    racine = _noor(tmp_path)
    dossier = ecrire_general(tmp_path / "general", en=True)
    chemin = quotidien.preparer_jour(racine, "noor", depuis_iso(LUNDI), False, dossier)
    entete, corps = lire(chemin)
    assert entete["langue"] == "en" and entete["prenom"] == "NOOR"
    assert "> One more step today." in corps and "## A word from Marius" in corps
    assert "## Word of the day · Romanian" in corps  # lundi 5 janvier : rang 0
    marius = quotidien.preparer_jour(racine, "marius", depuis_iso(LUNDI), False, dossier)
    assert "langue" not in lire(marius)[0]


def test_anglophone_sans_listes_le_ticket_sort_en_anglais(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = _noor(tmp_path)
    dossier = ecrire_general(tmp_path / "general", config=CONFIG_EN)  # pas de en/
    chemin = quotidien.preparer_jour(racine, "noor", depuis_iso(LUNDI), False, dossier)
    entete, corps = lire(chemin)
    assert entete["langue"] == "en" and "general" not in entete
    assert "> One more step today." in corps
    assert "partie générale absente" in capsys.readouterr().err


def test_le_matin_lit_la_bibliotheque_anglaise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    racine = _noor(tmp_path)
    surcouche_en(racine / "bibliotheque")
    dossier = ecrire_general(tmp_path / "general", en=True)
    chemin = quotidien.preparer_jour(racine, "noor", depuis_iso(LUNDI), False, dossier)
    entete, corps = lire(chemin)
    assert entete["nouvelle"] == "intervalle"  # seule racine de la carte de démonstration
    assert "## New · Interval\n" in corps and "The distance between two notes" in corps
    erreur = capsys.readouterr().err
    assert "traduction en manquante" in erreur and "concepts/accord-parfait" in erreur
