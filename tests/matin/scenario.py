"""Une racine de démonstration pour le rituel : deux élèves inscrits, configurations isolées."""

import shutil
from pathlib import Path

import pytest

from freinet import acces, eleves, imprimante
from tests.bibliotheque.demo import DEMO

LUNDI_6H = "2026-01-05T05:00:00+00:00"


def racine_matin(dossier: Path, noms: tuple[str, ...] = ("alice", "marius")) -> Path:
    shutil.copytree(DEMO, dossier / "bibliotheque")
    for nom in noms:
        assert eleves.main(["--racine", str(dossier), "ajouter", nom, "Europe/Paris"]) == 0
        assert eleves.main(["--racine", str(dossier), "inscrire", nom, "harmonie-demo"]) == 0
    return dossier


def configurer(monkeypatch: pytest.MonkeyPatch, dossier: Path, port: int | None) -> None:
    """L'imprimante (factice) et la page du QR du test, jamais celles du dépôt."""
    config = dossier / "imprimante.md"
    ip = f"| IP | 127.0.0.1 |\n| Port | {port} |\n" if port else "| IP | à renseigner |\n"
    config.write_text(ip, encoding="utf-8")
    monkeypatch.setattr(imprimante, "FICHIER_IMPRIMANTE", config)
    retour = dossier / "retour.md"
    retour.write_text("| Adresse du QR | http://mac.local:8765 |\n", encoding="utf-8")
    monkeypatch.setattr(acces, "FICHIER_RETOUR", retour)
