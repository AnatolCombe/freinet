import hashlib
from dataclasses import replace
from datetime import date
from pathlib import Path

from PIL import Image

from freinet.rendu_png import LARGEUR, couper, png_ticket, police
from freinet.ticket import Bloc, Ticket, lire_ticket
from tests.ticket.demo import REFERENCE, RETOUR, comparer_reference, plan_demo


def _empreinte(image: Image.Image) -> str:
    empreinte = hashlib.sha256(image.tobytes()).hexdigest()
    return f"{image.width}x{image.height} {image.mode} {empreinte}\n"


def test_png_de_reference(tmp_path: Path, update_ref: bool) -> None:
    chemin, bib = plan_demo(tmp_path)
    image = png_ticket(lire_ticket(chemin, bib, RETOUR))
    assert image.mode == "1" and image.width == LARGEUR  # 1 bit, 80 mm (#18)
    if update_ref:
        image.save(REFERENCE / "ticket-demo.png")  # à regarder ; le test compare l'empreinte
    comparer_reference("ticket-demo.png.sha256", _empreinte(image), update_ref)


def test_sans_qr_ni_reponses_le_ticket_est_plus_court(tmp_path: Path) -> None:
    chemin, bib = plan_demo(tmp_path)
    complet = png_ticket(lire_ticket(chemin, bib, RETOUR))
    nu = png_ticket(replace(lire_ticket(chemin, bib), reponses=()))
    assert nu.height < complet.height - 200


def test_un_long_ticket_allonge_la_bande() -> None:
    blocs = tuple(Bloc("texte", f"Ligne {n} " * 12) for n in range(60))
    blocs += (Bloc("quete", "Quête", None, (2, 4)),)  # barre à moitié pleine
    image = png_ticket(Ticket(date(2026, 1, 5), blocs, ()))
    assert image.height > 4000 and image.width == LARGEUR


def test_couper_au_mot_et_dans_un_mot_trop_long() -> None:
    fonte = police(False, 24)
    assert couper("un deux trois", fonte, 1000) == ["un deux trois"]
    assert couper("", fonte, 100) == []
    morceaux = couper("x" * 80, fonte, 200)
    assert len(morceaux) > 1 and "".join(morceaux) == "x" * 80
    assert all(fonte.getlength(m) <= 200 for m in morceaux)
