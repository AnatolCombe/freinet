from pathlib import Path

import pytest
import yaml

from freinet.import_projet import main, origine_de, projet_de, source_md
from tests.bibliotheque.demo import ecrire

COURS = """# Cours — Structure de saga

Voir https://fr.wikipedia.org/wiki/Kish%C5%8Dtenketsu, et McKee, Story (1997).

## PARTIE 1 : POURQUOI ?

### 1.1 Le problème

Texte (https://example.org/a).
"""


def test_projet_et_origine(tmp_path: Path) -> None:
    document = tmp_path / "ROMAN" / "making_off" / "COURS_SAGA.md"
    ecrire(document, COURS)
    assert projet_de(document) == "ROMAN"
    assert projet_de(tmp_path / "vrac" / "notes.md") == "vrac"
    assert origine_de(document).endswith("ROMAN/making_off/COURS_SAGA.md")


def test_source_md(tmp_path: Path) -> None:
    document = tmp_path / "ROMAN" / "making_off" / "COURS_SAGA.md"
    ecrire(document, COURS)
    texte = source_md(document)
    assert 'projet: "ROMAN"\n' in texte
    assert "- Cours — Structure de saga\n  - PARTIE 1 : POURQUOI ?\n    - 1.1 Le problème" in texte
    assert "- https://example.org/a\n- https://fr.wikipedia.org/wiki/Kish%C5%8Dtenketsu" in texte


def test_document_sans_titre_ni_url(tmp_path: Path) -> None:
    document = tmp_path / "notes.md"
    ecrire(document, "du texte\n")
    texte = source_md(document)
    assert "(aucun titre)" in texte and "(aucune URL)" in texte


def test_ligne_de_commande(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    document = tmp_path / "ROMAN" / "making_off" / "COURS_SAGA.md"
    ecrire(document, COURS)
    sortie = tmp_path / "out" / "source.md"
    assert main([str(document), "--sortie", str(sortie)]) == 0
    assert sortie.read_text(encoding="utf-8").startswith("---\ntype: source\n")
    assert str(sortie) in capsys.readouterr().out


def test_frontmatter_valide_quel_que_soit_le_chemin(tmp_path: Path) -> None:
    document = tmp_path / "a: b #c" / "making_off" / "COURS.md"
    ecrire(document, "# Titre\n")
    donnees = yaml.safe_load(source_md(document).split("---")[1])
    assert donnees["projet"] == "a: b #c"
    assert donnees["origine"].endswith("a: b #c/making_off/COURS.md")


def test_code_ignore_et_urls_a_parentheses(tmp_path: Path) -> None:
    document = tmp_path / "notes.md"
    ecrire(
        document,
        "# Vrai\n```\n# faux titre\nhttps://code.example.com\n```\n"
        "Voir https://fr.wikipedia.org/wiki/Foo_(bar)! et [x](https://a.org/p).\n",
    )
    texte = source_md(document)
    assert "faux titre" not in texte and "code.example.com" not in texte
    assert "- https://a.org/p\n- https://fr.wikipedia.org/wiki/Foo_(bar)\n" in texte


def test_source_existante_protegee(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    document = tmp_path / "notes.md"
    ecrire(document, "# Titre\n")
    sortie = tmp_path / "source.md"
    ecrire(sortie, "déjà complété par l'étape LLM\n")
    assert main([str(document), "--sortie", str(sortie)]) == 1
    assert "--force" in capsys.readouterr().out
    assert sortie.read_text(encoding="utf-8") == "déjà complété par l'étape LLM\n"
    assert main([str(document), "--sortie", str(sortie), "--force"]) == 0
    assert sortie.read_text(encoding="utf-8").startswith("---\ntype: source\n")
