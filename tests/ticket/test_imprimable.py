from freinet.imprimable import REMPLACEMENT, absents, imprimable


def test_couverture_de_la_police() -> None:
    assert absents("Élève, cœur, « ≥ 5 % », π, √2, x², ½, →, ✂, ﬁ") == ""
    assert absents("é") == ""  # composé en « é » (NFC)
    assert absents("漢 🎵 漢") == "漢🎵"


def test_caractere_absent_visible() -> None:
    assert imprimable("note 🎵 !") == f"note {REMPLACEMENT} !"
    assert imprimable("été") == "été"
