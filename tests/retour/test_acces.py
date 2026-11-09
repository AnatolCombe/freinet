import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from freinet import acces, quotidien, rendu
from freinet.acces import (
    ALPHABET_CODE,
    cle_acces,
    code_lisible,
    hacher,
    lire_config_retour,
    normaliser_code,
    nouvel_acces,
)
from freinet.base import Base
from freinet.bibliotheque import Bibliotheque
from freinet.ticket import Retour, Ticket, lire_ticket
from tests.retour.scenario import CONFIG, LUNDI, instant, passage, racine_demo


def test_nouvel_acces_aleatoire() -> None:
    tirages = {nouvel_acces() for _ in range(50)}
    assert len({a.jeton for a in tirages}) == 50 and len({a.code for a in tirages}) == 50
    a = next(iter(tirages))
    assert len(a.jeton) >= 22  # 16 octets en base64 url : 128 bits (A1)
    assert len(a.code) == 8 and set(a.code) <= set(ALPHABET_CODE)
    assert hacher(b"k", a.jeton) != hacher(b"autre", a.jeton)
    assert len(hacher(b"k", a.jeton)) == 64


def test_code_lisible_et_saisie() -> None:
    assert code_lisible("ABCDEFGH") == "ABCD-EFGH"
    assert normaliser_code(" abcd-efgh ") == "ABCDEFGH"
    assert normaliser_code("ééAB²01IO") == "AB"  # rien hors de l'alphabet du code (ASCII)


def test_meme_acces_pour_le_jour_nouveau_sur_demande(tmp_path: Path) -> None:
    racine = racine_demo(tmp_path)
    premier = passage(racine, LUNDI)
    assert passage(racine, LUNDI) == premier  # nouveau rendu : le ticket imprimé reste valable
    fichier = racine / "quotidien" / "03_rendu" / "output" / "marius" / "acces-2026-01-05.txt"
    assert fichier.stat().st_mode & 0o777 == 0o600
    cle = cle_acces(racine)
    assert cle_acces(racine) == cle  # créée une fois, relue ensuite
    assert (racine / "data" / ".cle-acces").stat().st_mode & 0o777 == 0o600
    with Base(racine / "data" / "freinet.db") as base:
        eleve = base.brainiac_par_nom("marius")
        assert eleve is not None
        assert base.acces_du_plan(eleve.brainiac_id, LUNDI) == (
            hacher(cle, premier.jeton),
            hacher(cle, premier.code),
        )
        dossier = fichier.parent
        renouvele = acces.acces_du_jour(base, eleve.brainiac_id, LUNDI, dossier, cle, True)
        assert renouvele != premier
        assert base.plan_par_acces(hacher(cle, premier.jeton), LUNDI) is None
        fichier.write_text("abîmé", encoding="utf-8")  # clair illisible : nouvel accès
        assert acces.acces_du_jour(base, eleve.brainiac_id, LUNDI, dossier, cle) != renouvele


def test_cle_abimee_refusee(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / ".cle-acces").write_text("", encoding="ascii")
    with pytest.raises(ValueError, match="clé d'accès abîmée"):
        cle_acces(tmp_path)


def test_config_retour(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chemin = tmp_path / "retour.md"
    chemin.write_text("| Port | 9000 |\n| Adresse du QR | auto |\n", encoding="utf-8")
    monkeypatch.setattr(acces, "nom_local", lambda: "mac.local")
    config = lire_config_retour(chemin)
    assert (config.ecoute, config.port, config.adresse) == (
        "0.0.0.0",
        9000,
        "http://mac.local:9000",
    )
    assert config.page_code == "mac.local:9000/c"
    chemin.write_text("| Adresse du QR | http://192.168.1.20:8765 |\n", encoding="utf-8")
    assert lire_config_retour(chemin).adresse == "http://192.168.1.20:8765"
    for ligne in ("| Port | 0 |", "| Adresse du QR | javascript:alert(1) |"):
        chemin.write_text(ligne + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="invalide"):
            lire_config_retour(chemin)


def test_nom_local(monkeypatch: pytest.MonkeyPatch) -> None:
    def scutil(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, "Mac-de-Marius\n", "")

    monkeypatch.setattr(subprocess, "run", scutil)
    assert acces.nom_local() == "Mac-de-Marius.local"

    def absent(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise OSError("pas de scutil (Linux)")

    monkeypatch.setattr(subprocess, "run", absent)
    monkeypatch.setattr(socket, "gethostname", lambda: "mac.home")
    assert acces.nom_local() == "mac.local"


def test_nom_local_sans_usr_sbin_dans_le_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """launchd lance le rituel et le serveur avec un PATH sans /usr/sbin : `scutil` est
    appelé par son chemin, sinon le QR pointerait vers le nom DHCP (`mac.local`)."""
    appels: list[list[str]] = []

    def scutil(commande: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        appels.append(commande)
        return subprocess.CompletedProcess(commande, 0, "Mac-de-Marius\n", "")

    monkeypatch.setattr(subprocess, "run", scutil)
    assert acces.nom_local() == "Mac-de-Marius.local"
    assert appels[0][0] == "/usr/sbin/scutil"


def test_qr_vers_adviza(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(acces, "nom_local", lambda: "mac.local")
    chemin = tmp_path / "retour.md"
    chemin.write_text("| Adresse du QR | auto |\n| QR vers ADVIZA | aucune |\n", "utf-8")
    config = lire_config_retour(chemin)
    assert config.adviza is None and config.lien_du_qr("abc") == "http://mac.local:8765/r/abc"
    chemin.write_text("| QR vers ADVIZA | http://adviza.local:8000 |\n", encoding="utf-8")
    lien = lire_config_retour(chemin).lien_du_qr("abc")
    assert lien == "http://adviza.local:8000/profil/freinet/aujourdhui"
    chemin.write_text("| QR vers ADVIZA | javascript:alert(1) |\n", encoding="utf-8")
    with pytest.raises(ValueError, match="QR vers ADVIZA invalide"):
        lire_config_retour(chemin)


def test_le_ticket_porte_le_lien_vers_adviza(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = racine_demo(tmp_path)
    arguments = ["--racine", str(racine), "--eleve", "marius", "--instant", instant(LUNDI)]
    assert quotidien.main(arguments) == 0
    liens: list[str] = []

    def espion(chemin: Path, bib: Bibliotheque, retour: Retour | None = None) -> Ticket:
        assert retour is not None
        liens.append(retour.lien)
        return lire_ticket(chemin, bib, retour)

    monkeypatch.setattr(rendu, "lire_ticket", espion)
    vers_adviza = replace(CONFIG, adviza="http://a.local:8000")
    rendu.rendre(racine, "marius", LUNDI, None, config=vers_adviza)
    rendu.rendre(racine, "marius", LUNDI, None, config=CONFIG)
    assert liens[0] == "http://a.local:8000/profil/freinet/aujourdhui"
    assert liens[1].startswith("http://freinet.local:8765/r/")  # sans réglage : inchangé
