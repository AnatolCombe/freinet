from pathlib import Path

import pytest

from freinet.frontmatter import ErreurContenu, lire, section
from tests.bibliotheque.demo import ecrire


def test_lit_frontmatter_et_corps(tmp_path: Path) -> None:
    fichier = tmp_path / "c.md"
    ecrire(fichier, "---\ntype: concept\nid: x\n---\n\n## Leçon\n\nCourt.\n")
    donnees, corps = lire(fichier)
    assert donnees == {"type": "concept", "id": "x"}
    assert section(corps, "Leçon") == "Court."


@pytest.mark.parametrize(
    ("texte", "message"),
    [
        ("pas de frontmatter\n", "absent"),
        ("---\ntype: concept\n", "non fermé"),
        ("---\n: : :\n---\n", "YAML invalide"),
        ("---\n- une liste\n---\n", "dictionnaire"),
        ("---\n---\n", "frontmatter vide"),
    ],
)
def test_fichier_mal_forme_refuse(tmp_path: Path, texte: str, message: str) -> None:
    fichier = tmp_path / "c.md"
    ecrire(fichier, texte)
    with pytest.raises(ErreurContenu, match=message) as erreur:
        lire(fichier)
    assert str(fichier) in str(erreur.value)


def test_section_s_arrete_au_titre_suivant() -> None:
    corps = "## Leçon\nA\n\n## Version longue\nB\n"
    assert section(corps, "Leçon") == "A"
    assert section(corps, "Version longue") == "B"
    assert section(corps, "Analogies") == ""


@pytest.mark.parametrize(
    ("brut", "lecon"),
    [
        (b"---\r\ntype: concept\r\n---\r\n\r\n## Le\xc3\xa7on\r\nCourt.\r\n", "Court."),
        (b"\xef\xbb\xbf---\ntype: concept\n---\n\n## Le\xc3\xa7on\nCourt.\n", "Court."),
        (b"---  \ntype: concept\n---", ""),
    ],
    ids=["fins-de-ligne-windows", "bom-utf8", "fermeture-sans-retour"],
)
def test_fichiers_reels_toleres(tmp_path: Path, brut: bytes, lecon: str) -> None:
    fichier = tmp_path / "c.md"
    fichier.write_bytes(brut)
    donnees, corps = lire(fichier)
    assert donnees == {"type": "concept"}
    assert section(corps, "Leçon") == lecon


def test_encodage_non_utf8_refuse(tmp_path: Path) -> None:
    fichier = tmp_path / "c.md"
    fichier.write_bytes(b"---\ntitre: \xff\xfe\n---\n")
    with pytest.raises(ErreurContenu, match="encodage non UTF-8"):
        lire(fichier)
