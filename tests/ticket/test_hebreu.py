from datetime import date

from freinet.imprimable import absents, visuel
from freinet.rendu_png import png_ticket
from freinet.ticket import Bloc, Ticket


def test_hebreu_dans_la_couverture() -> None:
    assert absents("פרגון שלום") == ""  # les 27 lettres (05D0-05EA) sont dans les deux graisses


def test_ordre_visuel() -> None:
    assert visuel("Firgun, פרגון.") == "Firgun, ןוגרפ."
    assert visuel("שלום עולם") == "םלוע םולש"  # deux mots : la suite entière est retournée
    assert visuel("Dor [dor]") == "Dor [dor]"


def test_hebreu_imprimable() -> None:
    hebreu = Ticket(date(2026, 1, 5), (Bloc("texte", "פרגון"),), ())
    rate = Ticket(date(2026, 1, 5), (Bloc("texte", "?????"),), ())
    assert png_ticket(hebreu).tobytes() != png_ticket(rate).tobytes()


def test_roumain_dans_la_couverture() -> None:
    assert absents("șțȘȚ") == ""  # virgule souscrite (U+0218-021B), pas la cédille ş ţ
