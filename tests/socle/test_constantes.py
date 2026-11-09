from pathlib import Path

import pytest

from freinet.constantes import ReglesAcquis, lire_regles


def test_lit_les_constantes_du_fichier_de_config() -> None:
    assert lire_regles() == ReglesAcquis(retention=0.85, horizon_jours=30, transferts_requis=1)


def test_constante_absente_refusee(tmp_path: Path) -> None:
    fichier = tmp_path / "regle-acquis.md"
    fichier.write_text("| `RETENTION_ACQUIS` | 0,85 — seule |\n", encoding="utf-8")
    with pytest.raises(ValueError, match="HORIZON_ACQUIS_JOURS"):
        lire_regles(fichier)


def _config(tmp_path: Path, retention: str, horizon: str = "30", transferts: str = "1") -> Path:
    fichier = tmp_path / "regle-acquis.md"
    fichier.write_text(
        f"| `RETENTION_ACQUIS` | {retention} — seuil |\n"
        f"| `HORIZON_ACQUIS_JOURS` | {horizon} — jours |\n"
        f"| `TRANSFERT_REQUIS` | {transferts} — transferts |\n",
        encoding="utf-8",
    )
    return fichier


def test_point_decimal_lu_sans_troncature(tmp_path: Path) -> None:
    assert lire_regles(_config(tmp_path, "0.85")).retention == 0.85


@pytest.mark.parametrize(
    ("retention", "horizon", "message"),
    [
        ("85", "30", "RETENTION_ACQUIS"),
        ("0", "30", "RETENTION_ACQUIS"),
        ("0,85", "0", "HORIZON_ACQUIS_JOURS"),
        ("85%", "30", "illisible"),
        ("0,85", "30,5", "illisible"),
    ],
)
def test_valeur_invalide_refusee(
    tmp_path: Path, retention: str, horizon: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        lire_regles(_config(tmp_path, retention, horizon))


def test_constante_en_double_refusee(tmp_path: Path) -> None:
    fichier = _config(tmp_path, "0,85")
    fichier.write_text(
        fichier.read_text(encoding="utf-8") + "| `RETENTION_ACQUIS` | 0,5 |\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="en double"):
        lire_regles(fichier)
