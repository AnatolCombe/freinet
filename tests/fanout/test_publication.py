import os
import shutil
from pathlib import Path

import pytest

from freinet.base import Base
from freinet.bibliotheque import charger
from freinet.publication import main, publier, verifier
from freinet.sources import lire_registre
from tests.bibliotheque.demo import DEMO, ecrire, surcouche_en
from tests.socle.fabrique import revue

REGISTRE = lire_registre()
SORTIES = (
    ("cartes", "02_carte"),
    ("quetes", "02_carte"),
    ("concepts", "03_redaction"),
    ("questions", "04_questions"),
)


def _fanout_depuis_demo(racine: Path) -> Path:
    """Un run de fan-out dont les sorties sont exactement la carte de démonstration."""
    fanout = racine / "fanout"
    for sous, etape in SORTIES:
        shutil.copytree(DEMO / sous, fanout / etape / "output" / sous)
    return fanout


def _bibliotheque_vide(racine: Path) -> Path:
    bibliotheque = racine / "bibliotheque"
    ecrire(bibliotheque / "index.md", "vide\n")
    return bibliotheque


def _renommer(fanout: Path, ancien: str, nouveau: str) -> None:
    """Réécrit tout le run comme si le fan-out avait renommé `ancien` en `nouveau`."""
    for fichier in sorted(fanout.rglob("*.md"), reverse=True):
        texte = fichier.read_text(encoding="utf-8").replace(ancien, nouveau)
        cible = Path(str(fichier).replace(ancien, nouveau))
        cible.parent.mkdir(parents=True, exist_ok=True)
        fichier.unlink()
        cible.write_text(texte, encoding="utf-8")
    concept = fanout / "03_redaction" / "output" / "concepts" / f"{nouveau}.md"
    concept.write_text(
        concept.read_text(encoding="utf-8").replace("alias: []", f"alias: [{ancien}]"),
        encoding="utf-8",
    )


def test_premiere_publication_puis_reutilisation(tmp_path: Path) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert publie, rapport
    assert "- créés : 22" in rapport
    assert set(charger(bibliotheque).concepts) == set(charger(DEMO).concepts)
    assert "| harmonie-demo | 4 |" in (bibliotheque / "index.md").read_text(encoding="utf-8")
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert publie and "- réutilisés à l'identique : 22" in rapport
    assert not (tmp_path / ".bibliotheque.publication").exists()


def test_enrichissement_et_contenu_cumulatif(tmp_path: Path) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    assert publier(fanout, bibliotheque, None, REGISTRE)[0]
    for sous, etape in SORTIES:
        shutil.rmtree(fanout / etape / "output" / sous)
    concept = DEMO / "concepts" / "intervalle.md"
    ecrire(
        fanout / "03_redaction" / "output" / "concepts" / "intervalle.md",
        concept.read_text(encoding="utf-8") + "\nEnrichi.\n",
    )
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert publie
    assert "- modifiés (enrichis) : 1\n  - concepts/intervalle.md" in rapport
    assert set(charger(bibliotheque).concepts) == set(charger(DEMO).concepts)


def test_renommage_par_alias(tmp_path: Path) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    assert publier(fanout, bibliotheque, None, REGISTRE)[0]
    base = tmp_path / "freinet.db"
    with Base(base) as ouverte:
        b = ouverte.ajouter_brainiac("marius", "Europe/Paris")
        ouverte.ajouter_revue(revue("r1", brainiac_id=b, concept_id="accord-parfait"))
    _renommer(fanout, "accord-parfait", "accord-majeur")
    publie, rapport = publier(fanout, bibliotheque, base, REGISTRE)
    assert publie, rapport
    assert "- retirés (renommés, alias conservé) : 1\n  - concepts/accord-parfait.md" in rapport
    bib = charger(bibliotheque)
    assert "accord-parfait" not in bib.concepts
    assert bib.canonique("accord-parfait") == "accord-majeur"


def test_refus_ne_touche_a_rien(tmp_path: Path) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    shutil.rmtree(fanout / "04_questions" / "output" / "questions" / "intervalle")
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert not publie
    assert "intervalle : 0 question(s)" in rapport
    assert not (bibliotheque / "concepts").exists()
    assert (bibliotheque / "index.md").read_text(encoding="utf-8") == "vide\n"


@pytest.mark.parametrize(
    ("preparation", "message"),
    [
        ("illisible", "frontmatter absent"),
        ("vide", "aucun fichier .md"),
        ("lien", "lien symbolique refusé"),
        ("sans-bibliotheque", "bibliothèque introuvable"),
    ],
)
def test_refus_propres(tmp_path: Path, preparation: str, message: str) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    concepts = fanout / "03_redaction" / "output" / "concepts"
    if preparation == "illisible":
        ecrire(concepts / "casse.md", "sans frontmatter\n")
    elif preparation == "vide":
        shutil.rmtree(fanout)
    elif preparation == "lien":
        ecrire(tmp_path / "secret.md", "hors du fan-out\n")
        os.symlink(tmp_path / "secret.md", concepts / "fuite.md")
    else:
        shutil.rmtree(bibliotheque)
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert not publie and message in rapport


def test_concept_cite_par_le_journal_absent_refuse(tmp_path: Path) -> None:
    base = tmp_path / "freinet.db"
    with Base(base) as ouverte:
        b = ouverte.ajouter_brainiac("marius", "Europe/Paris")
        ouverte.ajouter_revue(revue("r1", brainiac_id=b, concept_id="solfege"))
    avant = base.read_bytes()
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    publie, rapport = publier(fanout, bibliotheque, base, REGISTRE)
    assert not publie
    assert "solfege : concept cité par le journal et disparu (#20)" in rapport
    assert base.read_bytes() == avant  # lue en lecture seule, sans migration


def test_echec_pendant_l_echange_remet_tout_en_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    assert publier(fanout, bibliotheque, None, REGISTRE)[0]
    avant = {p.relative_to(bibliotheque): p.read_bytes() for p in bibliotheque.rglob("*.md")}
    concept = fanout / "03_redaction" / "output" / "concepts" / "intervalle.md"
    concept.write_text(concept.read_text(encoding="utf-8") + "\nEnrichi.\n", encoding="utf-8")
    vrai_replace, appels = os.replace, []

    def replace_fragile(source: Path, cible: Path) -> None:
        appels.append(source)
        if len(appels) == 4:
            raise OSError("disque plein")
        vrai_replace(source, cible)

    monkeypatch.setattr("freinet.publication.os.replace", replace_fragile)
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert not publie and "disque plein" in rapport
    apres = {p.relative_to(bibliotheque): p.read_bytes() for p in bibliotheque.rglob("*.md")}
    assert apres == avant


def test_ligne_de_commande(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    arguments = ["--fanout", str(fanout), "--bibliotheque", str(bibliotheque)]
    assert main([*arguments, "--base", str(tmp_path / "absente.db")]) == 0
    assert "# Publication" in capsys.readouterr().out
    ecrire(fanout / "03_redaction" / "output" / "concepts" / "casse.md", "sans frontmatter\n")
    assert main([*arguments, "--base", str(tmp_path / "absente.db")]) == 1
    assert "Publication refusée" in capsys.readouterr().err
    rapport = (fanout / "06_publication" / "output" / "publication.md").read_text(encoding="utf-8")
    assert rapport.startswith("# Publication refusée")


def test_verification_a_blanc(tmp_path: Path) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    sans_defaut, rapport = verifier(fanout, bibliotheque, REGISTRE)
    assert sans_defaut and "publiable" in rapport
    assert not (bibliotheque / "concepts").exists()
    shutil.rmtree(fanout / "04_questions" / "output" / "questions" / "intervalle")
    sans_defaut, rapport = verifier(fanout, bibliotheque, REGISTRE)
    assert not sans_defaut and "intervalle : 0 question(s)" in rapport


def test_ligne_de_commande_verifier_et_archiver(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    ecrire(fanout / "01_cadrage" / "output" / "cadrage.md", "cadrage\n")
    ecrire(fanout / "01_cadrage" / "output" / ".gitkeep", "")
    arguments = ["--fanout", str(fanout), "--bibliotheque", str(bibliotheque)]
    assert main([*arguments, "--verifier"]) == 0
    assert "publiable" in capsys.readouterr().out
    assert not (bibliotheque / "concepts").exists()
    assert main([*arguments, "--base", str(tmp_path / "absente.db")]) == 0
    archives = list((fanout / "_publies").iterdir())
    assert len(archives) == 1
    assert (archives[0] / "01_cadrage" / "cadrage.md").is_file()
    assert (archives[0] / "03_redaction" / "concepts" / "intervalle.md").is_file()
    assert (fanout / "01_cadrage" / "output" / ".gitkeep").is_file()
    assert not (fanout / "03_redaction" / "output" / "concepts").exists()
    assert "Sorties du run archivées" in capsys.readouterr().out


def _run_de_traduction(racine: Path) -> Path:
    """Un run qui ne contient que la traduction de démonstration."""
    fanout = racine / "fanout"
    copie = racine / "copie"
    shutil.copytree(DEMO, copie / "bibliotheque")
    shutil.copytree(
        surcouche_en(copie / "bibliotheque"), fanout / "07_traduction" / "output" / "en"
    )
    return fanout


def test_publier_une_traduction(tmp_path: Path) -> None:
    bibliotheque = tmp_path / "bibliotheque"
    shutil.copytree(DEMO, bibliotheque)
    publie, rapport = publier(_run_de_traduction(tmp_path), bibliotheque, None, REGISTRE)
    assert publie, rapport
    assert "en/concepts/intervalle.md" in rapport
    assert charger(bibliotheque, "en").concepts["intervalle"].titre == "Interval"
    assert charger(bibliotheque).concepts["intervalle"].titre == "Intervalle"


def test_traduction_de_structure_differente_refusee(tmp_path: Path) -> None:
    bibliotheque = tmp_path / "bibliotheque"
    shutil.copytree(DEMO, bibliotheque)
    fanout = _run_de_traduction(tmp_path)
    fichier = fanout / "07_traduction" / "output" / "en" / "concepts" / "intervalle.md"
    fichier.write_text(
        fichier.read_text(encoding="utf-8").replace("domaine: musique", "domaine: finance"),
        encoding="utf-8",
    )
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert not publie and "domaine différent" in rapport
    assert not (bibliotheque / "en").exists()  # rien n'a bougé


def test_renommage_retire_aussi_la_traduction(tmp_path: Path) -> None:
    fanout, bibliotheque = _fanout_depuis_demo(tmp_path), _bibliotheque_vide(tmp_path)
    assert publier(fanout, bibliotheque, None, REGISTRE)[0]
    en = bibliotheque / "en"  # une « traduction » identique au français d'accord-parfait
    (en / "concepts").mkdir(parents=True)
    shutil.copy(bibliotheque / "concepts" / "accord-parfait.md", en / "concepts")
    shutil.copytree(
        bibliotheque / "questions" / "accord-parfait", en / "questions" / "accord-parfait"
    )
    _renommer(fanout, "accord-parfait", "accord-majeur")
    publie, rapport = publier(fanout, bibliotheque, None, REGISTRE)
    assert publie, rapport
    assert "en/concepts/accord-parfait.md" in rapport
    assert not (en / "concepts" / "accord-parfait.md").exists()
    assert not (en / "questions" / "accord-parfait").exists()
