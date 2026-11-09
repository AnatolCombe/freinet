"""Les libellés que le code écrit lui-même, par langue de l'élève (PROF-12) : `fr` ou `en`.

Le contenu (leçons, questions, listes générales) arrive déjà dans la langue de l'élève
(bibliothèque, `_config/general/`) ; ici, seulement les titres du plan, ce que le ticket imprime
autour, la météo, les dates, les défis et la consigne du coach. Le plan porte sa langue
(`langue:`, absente = `fr`) et le ticket la relit. Les marques du plan (`[écrire : 2]`,
`[cadre : 5]`, `[séparation]`) ne s'impriment pas : elles sont communes. Les clés des
dictionnaires (moment de la pluie, direction du vent, nature d'un lien, langue d'un mot, type
d'énigme) sont les valeurs françaises que le reste du code manipule.
Voir `docs/architecture.md` (langue de l'élève).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

LANGUES = ("fr", "en")
LANGUE_PAR_DEFAUT = "fr"


@dataclass(frozen=True)
class Libelles:
    code: str
    # Titres du plan, relus par le ticket (`ticket.py`) pour reconnaître les sections.
    revisions: str
    nouveau: str  # préfixe : « Nouveau · <titre> »
    avant_de_lire: str
    demain: str
    anecdote: str
    serendipite: str
    defi: str
    quete: str
    meteo: str  # préfixe : « Météo · <ville> »
    mot_de: str  # préfixe : « Un mot de <prénom> »
    mot_du_jour: str  # gabarit {langue}
    ce_jour: str  # gabarit {date}
    enigme: str  # gabarit {jour} {type}
    notes: str
    # Phrases par défaut (inv. 7) et consigne du coach (`coach.py`).
    phrase_defaut: str
    phrase_reprise: str
    coach_systeme: str
    # Ce que le ticket imprime autour du plan.
    etiquette_enigme: str
    source: str  # gabarit {source}
    avertissement_finance: str
    reponses: str
    plier: str
    noter: str
    consigne: str  # gabarit {code} {page}
    retiens: str  # ouvre la dernière phrase d'une leçon (`_config/pedagogie.md`)
    # Dates.
    jours: tuple[str, ...]
    mois: tuple[str, ...]
    premier: str  # le 1er du mois
    avant_jc: str  # gabarit {annee}
    format_heure: str  # gabarit {h} {m}
    # Météo.
    meteo_temperature: str  # gabarit {minimum} {maximum} {vent} {direction}
    meteo_pluie: str  # gabarit {pluie}
    meteo_moment: str  # gabarit {moment}
    meteo_soleil: str  # gabarit {lever} {coucher}
    moments: dict[str, str]
    directions: dict[str, str]
    # Sélection (`selection.py`) et sérendipité.
    defis: tuple[str, ...]  # gabarit {titre}
    reprise: str  # gabarit {morceaux}
    reprise_separateur: str
    reprise_quete: str  # gabarit {objectif} {acquis} {total}
    reprise_reussite: str  # gabarit {titre}
    natures: dict[str, str]
    # Partie générale.
    langues_du_mot: dict[str, str]
    types_enigme: dict[str, str]

    def date_longue(self, jour: date) -> str:
        return f"{self.jours[jour.weekday()]} {jour.day} {self.mois[jour.month - 1]} {jour.year}"

    def jour_du_mois(self, jour: date) -> str:
        """« 1er octobre » ; en anglais « 1 October »."""
        quantieme = self.premier if jour.day == 1 else str(jour.day)
        return f"{quantieme} {self.mois[jour.month - 1]}"

    def annee(self, annee: int) -> str:
        return self.avant_jc.format(annee=-annee) if annee < 0 else str(annee)

    def heure(self, hh_mm: str) -> str:
        heures, minutes = hh_mm.split(":")
        return self.format_heure.format(h=int(heures), m=minutes)


FR = Libelles(
    code="fr",
    revisions="Révisions",
    nouveau="Nouveau",
    avant_de_lire="Avant de lire",
    demain="À lire pour demain",
    anecdote="Anecdote du café",
    serendipite="Sérendipité",
    defi="Défi du jour",
    quete="Quête",
    meteo="Météo",
    mot_de="Un mot de",
    mot_du_jour="Mot du jour · {langue}",
    ce_jour="Ce jour-là · {date}",
    enigme="Énigme du {jour} · {type}",
    notes="Notes",
    phrase_defaut="Un pas de plus aujourd'hui.",
    phrase_reprise="On reprend en douceur : rien à rattraper.",
    coach_systeme=(
        "Tu es le coach bienveillant d'un élève adulte qui lit son ticket d'étude imprimé au "
        "café, le matin. Réponds par UNE seule phrase en français, 90 caractères au plus, sans "
        "guillemets, sans lien, sans emoji, sans flatterie ni pression : un appui concret pour "
        "la journée, qui tient compte de ce qui suit."
    ),
    etiquette_enigme="Énigme",
    source="Source : {source}",
    avertissement_finance="éducatif, pas un conseil d'investissement",
    reponses="Réponses",
    plier="- - - - - - - ✂ plier ici - - - - - - - - - - -",
    noter="NOTER : scanne le QR,",
    consigne="ou tape le code {code} sur {page}",
    retiens="Retiens :",
    jours=("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    mois=(
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    premier="1er",
    avant_jc="{annee} av. J.-C.",
    format_heure="{h} h {m}",
    meteo_temperature="{minimum}° → {maximum}° · vent {vent} km/h {direction}",
    meteo_pluie="Pluie {pluie} %",
    meteo_moment=", surtout {moment}",
    meteo_soleil="Soleil {lever} → {coucher}",
    moments={m: m for m in ("la nuit", "le matin", "l'après-midi", "le soir")},
    directions={d: d for d in ("N", "NE", "E", "SE", "S", "SO", "O", "NO")},
    defis=(
        "Explique « {titre} » en une seule phrase, à voix haute.",
        "Trouve un contre-exemple à la leçon « {titre} ».",
        "Avant de relire « {titre} », prédis ce que tu en retiendras ; vérifie ce soir.",
        "Invente une énigme dont la réponse est « {titre} ».",
        "Trouve dans ta journée une situation qui ressemble à « {titre} ».",
        "Si tu croises « {titre} » aujourd'hui, alors note où, d'un mot.",
        "Ce soir, explique « {titre} » à ton élève imaginaire en trois phrases (Feynman).",
    ),
    reprise="On reprend ici — {morceaux}.",
    reprise_separateur=" ; ",
    reprise_quete="quête « {objectif} », {acquis}/{total}",
    reprise_reussite="dernière réussite : « {titre} »",
    natures={"analogie": "analogie", "contraste": "contraste", "meme_idee": "meme idee"},
    langues_du_mot={
        "roumain": "Roumain",
        "allemand": "Allemand",
        "anglais": "Anglais",
        "espagnol": "Espagnol",
        "hébreu": "Hébreu",
        "français": "Français",
    },
    types_enigme={"logique": "Logique", "mots": "Mots", "chiffres": "Chiffres"},
)

EN = Libelles(
    code="en",
    revisions="Review",
    nouveau="New",
    avant_de_lire="Before reading",
    demain="To read for tomorrow",
    anecdote="Coffee anecdote",
    serendipite="Serendipity",
    defi="Today's challenge",
    quete="Quest",
    meteo="Weather",
    mot_de="A word from",
    mot_du_jour="Word of the day · {langue}",
    ce_jour="On this day · {date}",
    enigme="{jour} puzzle · {type}",
    notes="Notes",
    phrase_defaut="One more step today.",
    phrase_reprise="Easing back in: nothing to catch up on.",
    coach_systeme=(
        "You are the kind coach of an adult learner who reads a printed study ticket at the "
        "café in the morning. Reply with ONE sentence in English, 90 characters at most, no "
        "quotes, no link, no emoji, no flattery or pressure: concrete support for the day, "
        "taking into account what follows."
    ),
    etiquette_enigme="Puzzle",
    source="Source: {source}",
    avertissement_finance="educational, not investment advice",
    reponses="Answers",
    plier="- - - - - - - ✂ fold here - - - - - - - - - - -",
    noter="RATE IT: scan the QR,",
    consigne="or type the code {code} at {page}",
    retiens="Remember:",
    jours=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    mois=(
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    premier="1",
    avant_jc="{annee} BC",
    format_heure="{h}:{m}",
    meteo_temperature="{minimum}° → {maximum}° · wind {vent} km/h {direction}",
    meteo_pluie="Rain {pluie}%",
    meteo_moment=", mostly {moment}",
    meteo_soleil="Sun {lever} → {coucher}",
    moments={
        "la nuit": "at night",
        "le matin": "in the morning",
        "l'après-midi": "in the afternoon",
        "le soir": "in the evening",
    },
    directions={
        "N": "N",
        "NE": "NE",
        "E": "E",
        "SE": "SE",
        "S": "S",
        "SO": "SW",
        "O": "W",
        "NO": "NW",
    },
    defis=(
        'Explain "{titre}" in a single sentence, out loud.',
        'Find a counterexample to the lesson "{titre}".',
        'Before rereading "{titre}", predict what you will remember; check tonight.',
        'Invent a riddle whose answer is "{titre}".',
        'Find a situation in your day that looks like "{titre}".',
        'If you run into "{titre}" today, note where, in one word.',
        'Tonight, explain "{titre}" to an imaginary student in three sentences (Feynman).',
    ),
    reprise="Picking up here — {morceaux}.",
    reprise_separateur="; ",
    reprise_quete='quest "{objectif}", {acquis}/{total}',
    reprise_reussite='last success: "{titre}"',
    natures={"analogie": "analogy", "contraste": "contrast", "meme_idee": "same idea"},
    langues_du_mot={
        "roumain": "Romanian",
        "allemand": "German",
        "anglais": "English",
        "espagnol": "Spanish",
        "hébreu": "Hebrew",
        "français": "French",
    },
    types_enigme={"logique": "Logic", "mots": "Words", "chiffres": "Numbers"},
)

_TABLES = {FR.code: FR, EN.code: EN}


def libelles(code: str) -> Libelles:
    """La table d'une langue ; `ValueError` si la langue n'est pas prise en charge."""
    try:
        return _TABLES[code]
    except KeyError:
        raise ValueError(f"langue inconnue : {code} ({' ou '.join(LANGUES)})") from None
