"""Une partie générale de test : config et trois listes minimales, écrites dans un dossier.

Rotation des mots : roumain a deux mots (dor, omenie), les autres langues un seul. Énigmes :
deux par type. Faits : les 366 jours, génériques sauf le 6 janvier et le 30 septembre.
"""

from datetime import date, timedelta
from pathlib import Path

import yaml

from freinet.general import ConfigGeneral, Listes, lire_config, lire_listes

ORIGINE = date(2026, 1, 5)  # un lundi
CONFIG: dict[str, object] = {
    "ville": "Lyon",
    "latitude": 45.74846,
    "longitude": 4.84671,
    "fuseau": "Europe/Paris",
    "origine": ORIGINE.isoformat(),
    "seuil_pluie": 20,
    "langues": ["roumain", "allemand", "anglais", "espagnol", "hébreu"],
    "eleves": {
        "marius": {"prenom": "MARIUS"},
        "noor": {"prenom": "NOOR", "mot_de": "Marius"},
    },
}


LANGUES_EN = ["roumain", "allemand", "français", "espagnol", "hébreu"]
CONFIG_EN: dict[str, object] = {
    **CONFIG,
    "langues_en": LANGUES_EN,
    "eleves": {
        "marius": {"prenom": "MARIUS"},
        "noor": {"prenom": "NOOR", "mot_de": "Marius", "langue": "en"},
    },
}


def _mot(ident: str, langue: str, forme: str, prononciation: str, sens: str) -> dict[str, str]:
    return {
        "id": ident,
        "langue": langue,
        "forme": forme,
        "prononciation": prononciation,
        "sens": sens,
        "question": "À quoi ce mot te fait-il penser aujourd'hui ?",
        "source": f"https://fr.wiktionary.org/wiki/{ident}",
    }


MOTS = [
    _mot("dor", "roumain", "Dor", "dor", "Le manque doux de quelqu'un d'absent."),
    _mot(
        "waldeinsamkeit",
        "allemand",
        "Waldeinsamkeit",
        "valt-aïn-zam-kaït",
        "La solitude de la forêt, choisie.",
    ),
    _mot("apricity", "anglais", "Apricity", "a-pri-si-ti", "La chaleur du soleil en hiver."),
    _mot("sobremesa", "espagnol", "Sobremesa", "so-bré-mé-sa", "Parler à table après le repas."),
    _mot("firgun", "hébreu", "פרגון", "firgoun", "Se réjouir du succès d'un autre."),
    _mot("omenie", "roumain", "Omenie", "o-mé-ni-é", "La bonté ordinaire, la décence humaine."),
]


def _word(ident: str, langue: str, forme: str, prononciation: str, sens: str) -> dict[str, str]:
    return {
        "id": ident,
        "langue": langue,
        "forme": forme,
        "prononciation": prononciation,
        "sens": sens,
        "question": "What does this word bring to mind today?",
        "source": f"https://en.wiktionary.org/wiki/{ident}",
    }


MOTS_EN = [
    _word("dor", "roumain", "Dor", "dor", "The sweet longing for someone absent."),
    _word(
        "waldeinsamkeit",
        "allemand",
        "Waldeinsamkeit",
        "vald-ine-zam-kite",
        "The chosen solitude of the forest.",
    ),
    _word("flaner", "français", "Flâner", "flah-nay", "To stroll with no goal, for pleasure."),
    _word(
        "sobremesa", "espagnol", "Sobremesa", "so-bray-may-sa", "Talking at the table after a meal."
    ),
    _word("firgun", "hébreu", "פרגון", "fir-goon", "Rejoicing in someone else's success."),
    _word("omenie", "roumain", "Omenie", "o-meh-nee-eh", "Ordinary kindness, human decency."),
]
ENIGMES_EN = [
    {
        "id": f"{t}-{n}",
        "type": t,
        "enonce": f"Puzzle {t} {n}?",
        "solution": f"Solution {t} {n}.",
        "source": "original",
    }
    for t in ("logique", "mots", "chiffres")
    for n in (1, 2)
]
ENIGMES = [
    {
        "id": f"{t}-{n}",
        "type": t,
        "enonce": f"Énigme {t} {n} ?",
        "solution": f"Solution {t} {n}.",
        "source": "originale",
    }
    for t in ("logique", "mots", "chiffres")
    for n in (1, 2)
]
ENIGMES[4] = {
    "id": "chiffres-1",
    "type": "chiffres",
    "enonce": "2, 3, 5, 9, 17, … Quel est le suivant ?",
    "solution": "33 (chaque écart double).",
    "source": "originale",
}


def faits() -> list[dict[str, object]]:
    jours = [date(2024, 1, 1) + timedelta(n) for n in range(366)]  # 2024 : bissextile
    par_jour = {f"{j:%m-%d}": _fait(f"{j:%m-%d}", 1900, f"Fait du {j:%d/%m}.") for j in jours}
    par_jour["01-06"] = _fait("01-06", 1412, "Naissance supposée de Jeanne d'Arc, à Domrémy.")
    par_jour["09-30"] = _fait("09-30", 1791, "Première de La Flûte enchantée, à Vienne.")
    return list(par_jour.values())


def faits_en() -> list[dict[str, object]]:
    jours = [date(2024, 1, 1) + timedelta(n) for n in range(366)]
    par_jour = {f"{j:%m-%d}": _fait(f"{j:%m-%d}", 1900, f"Fact of {j:%d/%m}.") for j in jours}
    par_jour["01-06"] = _fait("01-06", 1412, "Joan of Arc is believed to be born in Domrémy.")
    par_jour["09-30"] = _fait("09-30", 1791, "Premiere of The Magic Flute, in Vienna.")
    return list(par_jour.values())


def _fait(jour: str, annee: int, texte: str) -> dict[str, object]:
    return {"jour": jour, "annee": str(annee), "texte": texte, "source": "https://fr.wikipedia.org"}


def ecrire_general(dossier: Path, *, en: bool = False, **remplacements: object) -> Path:
    """Écrit les quatre fichiers ; `config=`, `mots=`, `faits=`, `enigmes=` remplacent un
    contenu entier (tests d'erreur). `en` : config `CONFIG_EN` et listes anglaises dans `en/`."""
    dossier.mkdir(parents=True, exist_ok=True)
    contenus: dict[Path, object] = {
        dossier / "general.md": remplacements.get("config", CONFIG_EN if en else CONFIG),
        dossier / "mots.md": {"mots": remplacements.get("mots", MOTS)},
        dossier / "ce-jour-la.md": {"faits": remplacements.get("faits", faits())},
        dossier / "enigmes.md": {"enigmes": remplacements.get("enigmes", ENIGMES)},
    }
    if en:
        (dossier / "en").mkdir(exist_ok=True)
        contenus[dossier / "en" / "mots.md"] = {"mots": MOTS_EN}
        contenus[dossier / "en" / "ce-jour-la.md"] = {"faits": faits_en()}
        contenus[dossier / "en" / "enigmes.md"] = {"enigmes": ENIGMES_EN}
    for chemin, donnees in contenus.items():
        yaml_texte = yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False)
        chemin.write_text(f"---\n{yaml_texte}---\n", encoding="utf-8")
    return dossier


def charger(dossier: Path, langue: str = "fr") -> tuple[ConfigGeneral, Listes]:
    config = lire_config(dossier / "general.md")
    return config, lire_listes(config, dossier, langue)
