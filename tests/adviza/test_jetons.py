from pathlib import Path

import pytest

from freinet import adviza_jetons, eleves
from freinet.adviza_jetons import empreinte, lire_config_adviza

TABLE = "| Port | 8766 |\n\n| brainiac_id | empreinte |\n|---|---|\n"
ID_M = "11111111-1111-4111-8111-111111111111"
ID_L = "22222222-2222-4222-8222-222222222222"


def test_lire_la_table(tmp_path: Path) -> None:
    chemin = tmp_path / "adviza.md"
    lignes = f"| {ID_M} | {empreinte('a' * 43)} |\n| {ID_L} | {empreinte('b' * 43)} |\n"
    chemin.write_text(TABLE + lignes, encoding="utf-8")
    config = lire_config_adviza(chemin)
    assert config.port == 8766
    assert config.eleve("a" * 43) == ID_M and config.eleve("b" * 43) == ID_L
    assert config.eleve("c" * 43) is None and config.eleve("") is None
    for texte, motif in (
        ("| Port | 70000 |\n", "port invalide"),
        (TABLE + f"| {ID_M} | {empreinte('a')} |\n| {ID_L} | {empreinte('a')} |\n", "double"),
    ):
        chemin.write_text(texte, encoding="utf-8")
        with pytest.raises(ValueError, match=motif):
            lire_config_adviza(chemin)


def test_nouveau_jeton(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert eleves.main(["--racine", str(tmp_path), "ajouter", "marius", "Europe/Paris"]) == 0
    capsys.readouterr()  # `ajouter` affiche le brainiac_id : on l'écarte
    chemin = tmp_path / "adviza.md"
    chemin.write_text(TABLE.rstrip("\n"), encoding="utf-8")  # fin de ligne absente : rattrapée
    arguments = ["--racine", str(tmp_path), "--config", str(chemin), "nouveau"]
    assert adviza_jetons.main([*arguments, "marius"]) == 0
    jeton = capsys.readouterr().out.split()[0]
    assert len(jeton) >= 43 and jeton not in chemin.read_text(encoding="utf-8")
    assert lire_config_adviza(chemin).eleve(jeton) is not None
    assert adviza_jetons.main([*arguments, "personne"]) == 1
    assert "élève inconnu : personne" in capsys.readouterr().err
