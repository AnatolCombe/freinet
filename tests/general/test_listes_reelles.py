from collections import Counter

from freinet.general import lire_config, lire_listes


def test_listes_reelles_valides_et_suffisantes() -> None:
    """Les listes figées de `_config/general/` passent le validateur et couvrent six mois."""
    config = lire_config()
    listes = lire_listes(config)
    par_langue = Counter(m.langue for m in listes.mots)
    assert all(par_langue[langue] >= 25 for langue in config.langues), par_langue
    par_type = Counter(e.type for e in listes.enigmes)
    assert par_type["logique"] >= 78 and par_type["mots"] >= 52 and par_type["chiffres"] >= 52
    assert len(listes.faits) == 366
    assert all(s.startswith("https://") for s in (m.source for m in listes.mots))
    assert all(f.source.startswith("https://fr.wikipedia.org/") for f in listes.faits.values())


def test_listes_anglaises_valides_et_suffisantes() -> None:
    """Les listes de `_config/general/en/` passent le validateur, au même volume que le français."""
    config = lire_config()
    fr, en = lire_listes(config), lire_listes(config, langue="en")
    assert config.langues_en == ("roumain", "allemand", "français", "espagnol", "hébreu")
    par_langue = Counter(m.langue for m in en.mots)
    assert all(par_langue[langue] >= 25 for langue in config.langues_en), par_langue
    assert {m.id for m in en.mots if m.langue != "français"} == {
        m.id for m in fr.mots if m.langue != "anglais"
    }  # mêmes mots, définis en anglais
    assert Counter(e.type for e in en.enigmes) == Counter(e.type for e in fr.enigmes)
    assert len(en.faits) == 366
    assert all(f.source.startswith("https://en.wikipedia.org/") for f in en.faits.values())
    assert all(s.startswith("https://") for s in (m.source for m in en.mots))
