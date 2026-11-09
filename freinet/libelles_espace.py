"""Les libellés de l'espace d'un ticket (page du QR), par langue du plan (PROF-12).

L'espace prend la langue du plan ; les pages ouvertes sans jeton (`/cours`, `/fiche/…`, `/c`)
et les messages d'erreur du serveur restent en français, lus par Marius seulement. Ce sont des
constantes du code : `pages.py` et `espace.py` les insèrent telles quelles (sauf onglets,
notes, états et natures, échappés comme avant), si bien qu'une page française ne change pas.
"""

from __future__ import annotations

from dataclasses import dataclass

from freinet.langue import LANGUES


@dataclass(frozen=True)
class LibellesEspace:
    code: str  # attribut `lang` de la page
    separateur: str  # « Avant : … » / « Before: … »
    onglets: tuple[str, str, str]  # Aujourd'hui · Ma carte · Cours
    notes: dict[int, str]
    etats: dict[str, str]
    ticket_du_matin: str
    titre_du_jour: str  # gabarit {jour}
    a_lire_demain: str
    notion_du_jour: str
    semaine: str  # gabarit {notes} {objectif}
    voir_ma_carte: str
    questions: str
    rien_a_noter: str
    joker_note: str  # gabarit {titre} (déjà échappé)
    joker_bouton: str  # gabarit {titre} (déjà échappé)
    question: str  # gabarit {n}
    voir_reponse: str
    revoir_lecon: str
    fiche_complete: str
    relire_fiche: str
    question_retiree: str
    ma_carte: str
    ou_j_en_suis: str
    aucune_carte_suivie: str
    page_inconnue: str
    bibliotheque: str
    tous_les_cours: str
    aucune_carte: str
    cours: str
    notions: str  # après un nombre
    titre_notions: str
    quetes: str
    avant: str
    ensuite: str
    voisines: str
    fiche: str
    lecon: str
    pour_comprendre: str
    analogies: str
    anecdotes: str
    sources: str
    source: str
    natures: dict[str, str]


ESPACE_FR = LibellesEspace(
    code="fr",
    separateur=" : ",
    onglets=("Aujourd'hui", "Ma carte", "Cours"),
    notes={1: "Raté", 2: "Difficile", 3: "Bien", 4: "Facile"},
    etats={
        "acquis": "acquise",
        "en_cours": "en cours",
        "debloque": "débloquée",
        "verrouille": "à venir",
    },  # fmt: skip
    ticket_du_matin="Ticket du matin",
    titre_du_jour="Ticket du {jour}",
    a_lire_demain="À lire pour demain",
    notion_du_jour="Notion du jour",
    semaine="Cette semaine : {notes} ticket(s) noté(s) sur {objectif} visés.",
    voir_ma_carte="Voir ma carte",
    questions="Questions",
    rien_a_noter="Rien à noter aujourd'hui.",
    joker_note="« {titre} » : noté comme déjà su ; question de transfert demain.",
    joker_bouton="Je sais déjà « {titre} »",
    question="Question {n}",
    voir_reponse="Voir la réponse",
    revoir_lecon="Revoir la leçon",
    fiche_complete="Fiche complète",
    relire_fiche="Relire la fiche",
    question_retiree="(question retirée)",
    ma_carte="Ma carte",
    ou_j_en_suis="Où j'en suis",
    aucune_carte_suivie="Aucune carte suivie pour l'instant.",
    page_inconnue="Page inconnue",
    bibliotheque="Bibliothèque",
    tous_les_cours="Tous les cours",
    aucune_carte="Aucune carte pour l'instant.",
    cours="Cours",
    notions="notions",
    titre_notions="Notions",
    quetes="Quêtes",
    avant="Avant",
    ensuite="Ensuite",
    voisines="Voisines",
    fiche="Fiche",
    lecon="Leçon",
    pour_comprendre="Pour comprendre",
    analogies="Analogies",
    anecdotes="Anecdotes",
    sources="Sources",
    source="Source",
    natures={"analogie": "Analogie", "contraste": "Contraste", "meme_idee": "Même idée"},
)

ESPACE_EN = LibellesEspace(
    code="en",
    separateur=": ",
    onglets=("Today", "My map", "Lessons"),
    notes={1: "Missed", 2: "Hard", 3: "Good", 4: "Easy"},
    etats={
        "acquis": "mastered",
        "en_cours": "in progress",
        "debloque": "unlocked",
        "verrouille": "coming up",
    },  # fmt: skip
    ticket_du_matin="Morning ticket",
    titre_du_jour="Ticket of {jour}",
    a_lire_demain="To read for tomorrow",
    notion_du_jour="Today's notion",
    semaine="This week: {notes} ticket(s) rated out of {objectif}.",
    voir_ma_carte="See my map",
    questions="Questions",
    rien_a_noter="Nothing to rate today.",
    joker_note='"{titre}": marked as already known; transfer question tomorrow.',
    joker_bouton='I already know "{titre}"',
    question="Question {n}",
    voir_reponse="Show the answer",
    revoir_lecon="Review the lesson",
    fiche_complete="Full sheet",
    relire_fiche="Reread the sheet",
    question_retiree="(question removed)",
    ma_carte="My map",
    ou_j_en_suis="Where I stand",
    aucune_carte_suivie="No map followed yet.",
    page_inconnue="Unknown page",
    bibliotheque="Library",
    tous_les_cours="All lessons",
    aucune_carte="No map yet.",
    cours="Lessons",
    notions="concepts",
    titre_notions="Concepts",
    quetes="Quests",
    avant="Before",
    ensuite="Next",
    voisines="Neighbours",
    fiche="Sheet",
    lecon="Lesson",
    pour_comprendre="To understand",
    analogies="Analogies",
    anecdotes="Anecdotes",
    sources="Sources",
    source="Source",
    natures={"analogie": "Analogy", "contraste": "Contrast", "meme_idee": "Same idea"},
)

_TABLES = {ESPACE_FR.code: ESPACE_FR, ESPACE_EN.code: ESPACE_EN}


def libelles_espace(code: str) -> LibellesEspace:
    try:
        return _TABLES[code]
    except KeyError:
        raise ValueError(f"langue inconnue : {code} ({' ou '.join(LANGUES)})") from None
