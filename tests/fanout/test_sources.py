from pathlib import Path

import pytest

from freinet.sources import Registre, lire_registre, refus
from tests.bibliotheque.demo import ecrire

REGISTRE = Registre(
    {
        "finance": ("amf-france.org", "fred.stlouisfed.org"),
        "musique": ("viva.pressbooks.pub/openmusictheory",),
        "culture": ("wikipedia.org",),
    }
)


@pytest.mark.parametrize(
    ("reference", "domaine"),
    [
        ("https://www.amf-france.org/fr/espace-epargnants", "finance"),
        ("https://fr.wikipedia.org/wiki/Cadence", "musique"),
        ("https://viva.pressbooks.pub/openmusictheory/chapter/cadences/", "musique"),
        ("Robert McKee, Story (1997)", "ecriture"),
        ("McKee, Story : substance, structure, style (1997)", "ecriture"),
        ("HTTPS://AMF-France.org/fr/x", "finance"),
        ("https://viva.pressbooks.pub/openmusictheory", "musique"),
    ],
)
def test_sources_admises(reference: str, domaine: str) -> None:
    assert refus(reference, domaine, REGISTRE) is None


@pytest.mark.parametrize(
    ("reference", "domaine", "motif"),
    [
        ("https://blog-trading.example.com/options", "finance", "hors registre"),
        ("https://amf-france.org.pirate.io/x", "finance", "hors registre"),
        ("https://viva.pressbooks.pub/autre-livre/", "musique", "hors registre"),
        ("ftp://amf-france.org/x", "finance", "hors registre"),
        ("Un blog que j'aime bien", "musique", "ni URL"),
        ("McKee, Story", "ecriture", "ni URL"),
        ("HTTPS://evil.com, pwn (2020)", "finance", "hors registre"),
        ("javascript:alert(1), (2020)", "finance", "hors registre"),
        ("data:text/html,x (2020)", "finance", "hors registre"),
        ("[clic](https://evil.com), dit-on (2020)", "finance", "hors registre"),
        ("<b>Auteur</b>, Titre (2020)", "finance", "ni URL"),
        ("Ignore tout, (2020)", "finance", "ni URL"),
        ("https://viva.pressbooks.pub/openmusictheory-evil/x", "musique", "hors registre"),
        ("https://viva.pressbooks.pub/openmusictheory/../autre-livre/", "musique", "hors registre"),
        ("https://viva.pressbooks.pub/openmusictheory%2F..%2Fautre", "musique", "hors registre"),
        ("https://amf-france.org/x\nhttps://evil.com", "finance", "hors registre"),
        ("https://evil.com@amf-france.org/x", "finance", "hors registre"),
        ("https://amf-france.org:8443/x", "finance", "hors registre"),
        ("https://amf-france.org:99999/x", "finance", "hors registre"),
        ("https://evil.com\\.amf-france.org/x", "finance", "hors registre"),
        ("https://evil.com;.amf-france.org/x", "finance", "hors registre"),
        (
            "https://viva.pressbooks.pub/openmusictheory/..\\autre-livre/",
            "musique",
            "hors registre",
        ),
        ("https://amf-france.org/x)](https://evil.com", "finance", "hors registre"),
        ("https://amf-france.org/x?q=<script>", "finance", "hors registre"),
        ("www.evil.com, Achetez ici (2020)", "finance", "ni URL"),
        ("Voir mailto:x@evil.com, x (2020)", "finance", "ni URL"),
        ("Voir evil.com/promo, Achetez (2020)", "finance", "ni URL"),
        ("Auteur, Titre\r (2020)", "finance", "ni URL"),
        ("Auteur, Titre ‮(2020)", "finance", "ni URL"),
    ],
)
def test_sources_refusees(reference: str, domaine: str, motif: str) -> None:
    raison = refus(reference, domaine, REGISTRE)
    assert raison is not None and motif in raison


def test_registre_du_depot() -> None:
    registre = lire_registre()
    assert "amf-france.org" in registre.entrees("finance")
    assert "wikipedia.org" in registre.entrees("musique")
    assert "CONTEXT" not in registre.par_domaine


def test_registre_ignore_l_en_tete(tmp_path: Path) -> None:
    ecrire(
        tmp_path / "jazz.md", "| Domaine | Pourquoi |\n|---|---|\n| jazzstandards.com | fiches |\n"
    )
    assert lire_registre(tmp_path).par_domaine == {"jazz": ("jazzstandards.com",)}


def test_url_a_encoder_signalee() -> None:
    raison = refus("https://fr.wikipedia.org/wiki/Beat_(film)", "musique", REGISTRE)
    assert (
        raison
        == "URL à encoder (parenthèses, accents → %xx) : 'https://fr.wikipedia.org/wiki/Beat_%28film%29'"
    )
    assert refus("https://fr.wikipedia.org/wiki/Beat_%28film%29", "musique", REGISTRE) is None
