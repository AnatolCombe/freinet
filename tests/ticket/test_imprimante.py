from pathlib import Path

import pytest
from PIL import Image

from freinet.imprimante import (
    AVANCER_ET_COUPER,
    INITIALISER,
    Imprimante,
    ImprimanteIndisponible,
    ImprimanteUSB,
    envoyer,
    escpos,
    etat_papier,
    imprimante,
    lire_imprimante,
)
from tests.ticket.fausse_imprimante import Etat, fausse_imprimante, port_ferme
from tests.ticket.fausse_usb import ouvrir_pont

TRANSPORTS = ["tcp", "usb"]


def _envoyer(transport: str, port: int, fin: float = 90.0) -> None:
    if transport == "usb":
        envoyer(b"ticket", ImprimanteUSB(), fin=fin, ouvrir=ouvrir_pont(port))
    else:
        envoyer(b"ticket", Imprimante("127.0.0.1", port), fin=fin)


def test_raster_par_bandes() -> None:
    image = Image.new("1", (576, 300), 1)
    image.putpixel((0, 0), 0)  # un point noir en haut à gauche
    donnees = escpos(image)
    assert donnees.startswith(INITIALISER) and donnees.endswith(AVANCER_ET_COUPER)
    premiere = len(INITIALISER)
    assert donnees[premiere : premiere + 8] == b"\x1dv0\x00" + bytes([72, 0, 0, 1])  # 256 lignes
    assert donnees[premiere + 8] == 0x80  # le point noir = bit de poids fort à 1
    assert donnees.count(b"\x1dv0\x00") == 2  # 256 + 44 lignes
    attendu = len(INITIALISER) + 2 * 8 + 72 * 300 + len(AVANCER_ET_COUPER)
    assert len(donnees) == attendu


def test_largeur_non_multiple_de_huit_completee_en_blanc() -> None:
    donnees = escpos(Image.new("1", (10, 1), 0))
    assert donnees[len(INITIALISER) : len(INITIALISER) + 10] == (
        b"\x1dv0\x00" + bytes([2, 0, 1, 0]) + bytes([0xFF, 0xC0])
    )


@pytest.mark.parametrize("transport", TRANSPORTS)
@pytest.mark.parametrize(
    "etat", [Etat(), Etat(asb=True), Etat(parasite=True)], ids=["simple", "asb", "parasite"]
)
def test_envoi_confirme_par_l_imprimante(etat: Etat, transport: str) -> None:
    """Un état automatique (ASB) ou la réponse à un DLE EOT fortuit ne font pas échouer."""
    with fausse_imprimante(etat) as fausse:
        _envoyer(transport, fausse.port)
    assert fausse.recus == [b"ticket"]


@pytest.mark.parametrize("transport", TRANSPORTS)
@pytest.mark.parametrize(
    ("etat", "message"),
    [
        (Etat(imprimante=0x1A, cause=0x16), "capot ouvert"),
        (Etat(imprimante=0x1A, cause=0x32), "plus de papier"),
        (Etat(imprimante=0x1A, cause=0x52), "en erreur"),
        (Etat(imprimante=0x1A), "hors ligne"),
        (Etat(papier=0x72), "plus de papier"),
        (Etat(confirmation=0x0C), "papier épuisé pendant l'impression"),
        (Etat(confirmation=0x90), "confirmation inattendue"),
        (Etat(imprimante=0x00), "réponse d'état inattendue"),
    ],
)
def test_ticket_non_sorti(etat: Etat, message: str, transport: str) -> None:
    with fausse_imprimante(etat) as fausse, pytest.raises(ImprimanteIndisponible, match=message):
        _envoyer(transport, fausse.port)


@pytest.mark.parametrize("transport", TRANSPORTS)
def test_imprimante_muette(transport: str) -> None:
    """Elle accepte les données sans jamais confirmer (bourrage) : pas « imprimé »."""
    with fausse_imprimante(Etat(muette=True)) as fausse, pytest.raises(TimeoutError):
        _envoyer(transport, fausse.port, fin=0.5)


@pytest.mark.parametrize(("etat", "attendu"), [(Etat(), "ok"), (Etat(papier=0x1E), "bientôt fini")])
def test_etat_papier_par_usb(etat: Etat, attendu: str) -> None:
    with fausse_imprimante(etat) as fausse:
        assert etat_papier(ImprimanteUSB(), ouvrir=ouvrir_pont(fausse.port)) == attendu


def test_imprimante_eteinte() -> None:
    with pytest.raises(OSError):
        envoyer(b"ticket", Imprimante("127.0.0.1", port_ferme()), delai=2)


@pytest.mark.parametrize(
    ("adresse", "attendu"),
    [
        ("192.168.1.50", Imprimante("192.168.1.50")),
        ("192.168.1.50:9101", Imprimante("192.168.1.50", 9101)),
        ("tm-m30.local", Imprimante("tm-m30.local")),
        ("usb", ImprimanteUSB()),
        ("USB", ImprimanteUSB()),
    ],
)
def test_adresse(adresse: str, attendu: object) -> None:
    assert imprimante(adresse) == attendu


@pytest.mark.parametrize("adresse", ["", "999.1.1.1", "a b", "hote:0", "hote:x", "-x"])
def test_adresse_refusee(adresse: str) -> None:
    with pytest.raises(ValueError, match="invalide"):
        imprimante(adresse)


def test_config(tmp_path: Path) -> None:
    chemin = tmp_path / "imprimante.md"
    chemin.write_text("| Clé | Valeur |\n|---|---|\n| IP | à renseigner (…) |\n", "utf-8")
    with pytest.raises(ValueError, match="à renseigner"):
        lire_imprimante(chemin)
    chemin.write_text("| IP | 192.168.1.50 |\n| Port | 9100 |\n", encoding="utf-8")
    assert lire_imprimante(chemin) == Imprimante("192.168.1.50", 9100)
    chemin.write_text("| IP | 10.0.0.7 |\n", encoding="utf-8")
    assert lire_imprimante(chemin) == Imprimante("10.0.0.7", 9100)


def test_config_usb(tmp_path: Path) -> None:
    chemin = tmp_path / "imprimante.md"
    chemin.write_text("| Connexion | usb |\n| IP | à renseigner |\n", encoding="utf-8")
    assert lire_imprimante(chemin) == ImprimanteUSB()
    chemin.write_text("| Connexion | ethernet |\n| IP | 10.0.0.7 |\n", encoding="utf-8")
    assert lire_imprimante(chemin) == Imprimante("10.0.0.7", 9100)
    chemin.write_text("| Connexion | bluetooth |\n", encoding="utf-8")
    with pytest.raises(ValueError, match="connexion"):
        lire_imprimante(chemin)
