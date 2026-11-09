"""`quotidien/01_selection` : les items du jour, sans LLM et reproductibles (inv. 6).

Même graine (date logique + élève) et même état → même sélection. Révisions échues les plus
fragiles d'abord, plafonnées par la dose (#50, inv. 14) ; une question par concept, la moins
récemment posée (le format tourne, A8) ; une notion nouvelle par jour, jamais deux fois,
dont l'origine est tirée selon le dosage (projets / déclarés / sérendipité — le week-end,
100 % sérendipité, A2) ; notion présentée mais jamais notée = premier rappel le lendemain ;
lien latéral (#8) ; défi au format tournant (#24) ; reprise après une pause en jours logiques
(#11). Une question non notée reste simplement due (inv. 15).
"""

from __future__ import annotations

import random
from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from freinet.bibliotheque import Bibliotheque
from freinet.contenu import Carte, Question
from freinet.dose import Dose
from freinet.graphe import etats_maitrise, ordre_deblocage
from freinet.langue import FR, Libelles
from freinet.modele import EtatConcept, Inscription, Revue
from freinet.planification import depuis_json, retention
from freinet.rejeu import effectives
from freinet.temps import date_logique

NOTE_REUSSIE = 3


@dataclass(frozen=True)
class Item:
    concept_id: str
    question_id: str
    nature: str
    enonce: str


@dataclass(frozen=True)
class Nouvelle:
    concept_id: str
    titre: str
    lecon: str
    pre_test: Item | None


@dataclass(frozen=True)
class Serendipite:
    de: str
    vers: str
    nature: str


@dataclass(frozen=True)
class AnecdoteDuJour:
    concept_id: str
    texte: str
    source: str


@dataclass(frozen=True)
class QueteProgres:
    quete_id: str
    objectif: str
    acquis: int
    total: int


@dataclass(frozen=True)
class Selection:
    jour: date
    brainiac_id: str
    graine: str
    reprise: bool
    revisions: tuple[Item, ...]
    nouvelle: Nouvelle | None
    serendipite: Serendipite | None
    anecdote: AnecdoteDuJour | None
    defi: str | None
    quete: QueteProgres | None
    fil_ariane: str | None


def _item(question: Question) -> Item:
    return Item(question.concept, question.id, question.nature, question.enonce)


def _question_du_jour(
    questions: list[Question], dernieres: dict[str, datetime], reprise: bool
) -> Question:
    """La moins récemment posée ; en reprise, la plus facile (#11)."""
    if reprise:
        return min(questions, key=lambda q: (q.difficulte, q.id))
    jamais = datetime.min.replace(tzinfo=UTC)
    return min(questions, key=lambda q: (dernieres.get(q.id, jamais), q.id))


def _revisions(
    bib: Bibliotheque,
    etats: dict[str, EtatConcept],
    presentes_sans_etat: set[str],
    revues: list[Revue],
    fin_du_jour: datetime,
    nombre: int,
    reprise: bool,
    jokers: set[str],
) -> tuple[Item, ...]:
    """Les concepts échus les plus fragiles d'abord (fragilité mesurée à la fin du jour
    logique : deux impressions le même jour donnent la même liste). Une notion présentée mais
    jamais notée passe en premier rappel, en tête ; déclarée « je sais déjà » (#26), ce premier
    rappel est une question de transfert."""
    dernieres: dict[str, datetime] = {}
    for r in revues:
        dernieres[r.question_id] = max(r.repondu_le, dernieres.get(r.question_id, r.repondu_le))
    echus = [(-1.0, concept_id) for concept_id in presentes_sans_etat]
    for concept_id, etat in etats.items():
        carte = depuis_json(etat.carte_json)
        if carte.due < fin_du_jour:
            echus.append((retention(carte, fin_du_jour), concept_id))
    items: list[Item] = []
    for _fragilite, concept_id in sorted(echus):
        questions = [
            q for q in bib.questions.values() if q.concept == concept_id and q.nature != "pre_test"
        ]
        if concept_id in jokers and concept_id in presentes_sans_etat:
            questions = [q for q in questions if q.nature == "transfert"] or questions
        if questions and len(items) < nombre:
            items.append(_item(_question_du_jour(questions, dernieres, reprise)))
    return tuple(items)


def _presenter(bib: Bibliotheque, concept_id: str) -> Nouvelle:
    """La notion telle que le ticket la présente, avec son pré-test (#7) s'il existe."""
    concept = bib.concepts[concept_id]
    pre_tests = sorted(
        (q for q in bib.questions.values() if q.concept == concept.id and q.nature == "pre_test"),
        key=lambda q: q.id,
    )
    return Nouvelle(
        concept.id, concept.titre, concept.lecon, _item(pre_tests[0]) if pre_tests else None
    )


def _nouvelle(
    bib: Bibliotheque,
    cartes: list[Carte],
    acquis: set[str],
    deja_vus: set[str],
    categorie: str,
) -> Nouvelle | None:
    """Premier concept débloqué, jamais présenté, de la catégorie tirée : « projets » (issu
    d'un projet, B28), « déclarés » (les autres), « sérendipité » (atteint par un lien
    latéral depuis un concept déjà vu, #8). Si la catégorie tirée est vide, le premier débloqué,
    même sans lien latéral (ex. le samedi sans voisin)."""
    debloques = []
    for carte in cartes:
        etats = etats_maitrise(carte, acquis, deja_vus - acquis)
        debloques += [c for c in ordre_deblocage(carte) if etats[c] == "debloque"]
    debloques = [c for c in dict.fromkeys(debloques) if c in bib.concepts and c not in deja_vus]
    voisins = {
        bout
        for carte in cartes
        for lien in carte.lateraux
        if lien.de in deja_vus or lien.vers in deja_vus
        for bout in (lien.de, lien.vers)
    }
    par_categorie = {
        "projets": [c for c in debloques if bib.concepts[c].projet is not None],
        "declares": [c for c in debloques if bib.concepts[c].projet is None],
        "serendipite": [c for c in debloques if c in voisins],
    }
    choix = (par_categorie[categorie] or debloques)[:1]
    if not choix:
        return None
    return _presenter(bib, choix[0])


def selectionner(
    bib: Bibliotheque,
    etats: list[EtatConcept],
    revues: list[Revue],
    inscriptions: list[Inscription],
    brainiac_id: str,
    fuseau: str,
    dosage: tuple[int, int, int],
    dose: Dose,
    maintenant: datetime,
    presentes: Mapping[str, date] | None = None,
    jokers: Collection[str] = (),
    promesse: str | None = None,
    libelles: Libelles = FR,
) -> Selection:
    """`presentes` : les notions nouvelles des plans des jours précédents, avec le premier jour
    où chacune a été présentée (`Base.concepts_presentes`) ; `jokers` : celles déclarées « je
    sais déjà » sur la page du QR (`Base.concepts_joker`) ; `promesse` : la notion annoncée
    par le plan de la veille (#126), présentée en priorité si elle est dans la carte et jamais
    présentée ; `libelles` : la langue du défi et du fil d'Ariane (PROF-12)."""
    jour = date_logique(maintenant, fuseau)
    graine = f"{jour.isoformat()}:{brainiac_id}"
    hasard = random.Random(graine)
    fin_du_jour = datetime.combine(jour + timedelta(days=1), time(), ZoneInfo(fuseau))
    revues = [r for r in revues if r.brainiac_id == brainiac_id]
    # Tout scan compte comme un retour, même s'il ne contient qu'une correction.
    derniere_saisie = max((r.saisi_le for r in revues), default=None)
    revues = effectives(revues)
    cartes = [bib.cartes[i.carte_id] for i in inscriptions if i.carte_id in bib.cartes]
    travail = {c for carte in cartes for c in carte.concepts}
    par_concept = {
        e.concept_id: e for e in etats if e.concept_id in travail and e.brainiac_id == brainiac_id
    }
    acquis = {c for c, e in par_concept.items() if e.acquis_le is not None}
    en_cours = set(par_concept) - acquis
    # Le journal garde l'identifiant d'origine : une notion renommée reste « présentée » (#20).
    canoniques: dict[str, date] = {}
    for concept_id, premier in (presentes or {}).items():
        c = bib.canonique(concept_id)
        canoniques[c] = min(premier, canoniques.get(c, premier))
    presentes = canoniques
    presentes_sans_etat = {c for c in presentes if c in travail and c not in par_concept}

    # Reprise (#11) : du travail attendait une réponse (révision échue, notion présentée jamais
    # notée) et rien n'a été scanné depuis `reprise_jours`. Sans rien d'échu, jamais de reprise :
    # un élève à jour n'a rien à scanner, et une nouvelle carte lui donne ses notions.
    attentes = [presentes[c] for c in presentes_sans_etat]
    for etat in par_concept.values():
        due = depuis_json(etat.carte_json).due
        if due < fin_du_jour:
            attentes.append(date_logique(due, fuseau))
    reprise = False
    if attentes:
        reference = min(attentes)
        if derniere_saisie is not None:
            reference = max(reference, date_logique(derniere_saisie, fuseau))
        reprise = (jour - reference).days >= dose.reprise_jours
    revisions = _revisions(
        bib,
        par_concept,
        presentes_sans_etat,
        revues,
        fin_du_jour,
        dose.revisions,
        reprise,
        {bib.canonique(c) for c in jokers},
    )

    deja_vus = acquis | en_cours | (set(presentes) & travail)
    nouvelle = None
    if not reprise and dose.nouvelles > 0:
        poids = [max(0, p) for p in (dose.week_end if jour.weekday() >= 5 else dosage)]
        categorie = (
            hasard.choices(("projets", "declares", "serendipite"), weights=poids)[0]
            if sum(poids) > 0
            else "serendipite"
        )
        nouvelle = _nouvelle(bib, cartes, acquis, deja_vus, categorie)
        if promesse:
            promise = bib.canonique(promesse)
            if promise in bib.concepts and promise in travail and promise not in deja_vus:
                nouvelle = _presenter(bib, promise)

    connus = deja_vus | ({nouvelle.concept_id} if nouvelle else set())
    lateraux = sorted(
        (lien for carte in cartes for lien in carte.lateraux),
        key=lambda lien: (lien.de, lien.vers, lien.nature),
    )
    proches = [lien for lien in lateraux if lien.de in connus or lien.vers in connus]
    lien = hasard.choice(proches or lateraux) if (proches or lateraux) else None
    serendipite = Serendipite(lien.de, lien.vers, lien.nature) if lien else None

    priorite = [nouvelle.concept_id] if nouvelle else []
    # Les concepts du jour d'abord, puis ceux déjà vus, puis toute la carte : il y a toujours
    # une anecdote du café si la carte en contient une.
    priorite += [i.concept_id for i in revisions] + sorted(connus) + sorted(travail)
    anecdote = None
    for concept_id in dict.fromkeys(priorite):
        concept = bib.concepts.get(concept_id)
        if concept and concept.anecdotes:
            choisie = hasard.choice(concept.anecdotes)
            anecdote = AnecdoteDuJour(concept_id, choisie.texte, choisie.source)
            break

    sujet = nouvelle.concept_id if nouvelle else (revisions[0].concept_id if revisions else None)
    defi = None
    if sujet is not None:
        defi = libelles.defis[jour.toordinal() % len(libelles.defis)].format(
            titre=bib.concepts[sujet].titre
        )

    quete = None
    for inscription in inscriptions:
        q = bib.quetes.get(inscription.quete_active or "")
        if q is not None:
            quete = QueteProgres(
                q.id, q.objectif, sum(c in acquis for c in q.chemin), len(q.chemin)
            )
            break

    fil_ariane = None
    if reprise:
        reussies = [r for r in revues if r.note >= NOTE_REUSSIE and r.nature != "pre_test"]
        derniere = max(reussies, key=lambda r: (r.repondu_le, r.revue_id), default=None)
        morceaux = []
        if quete:
            morceaux.append(
                libelles.reprise_quete.format(
                    objectif=quete.objectif, acquis=quete.acquis, total=quete.total
                )
            )
        if derniere and bib.canonique(derniere.concept_id) in bib.concepts:
            titre = bib.concepts[bib.canonique(derniere.concept_id)].titre
            morceaux.append(libelles.reprise_reussite.format(titre=titre))
        fil_ariane = (
            libelles.reprise.format(morceaux=libelles.reprise_separateur.join(morceaux))
            if morceaux
            else None
        )

    return Selection(
        jour,
        brainiac_id,
        graine,
        reprise,
        revisions,
        nouvelle,
        serendipite,
        anecdote,
        defi,
        quete,
        fil_ariane,
    )


def notion_de_demain(
    bib: Bibliotheque,
    etats: list[EtatConcept],
    revues: list[Revue],
    inscriptions: list[Inscription],
    brainiac_id: str,
    fuseau: str,
    dosage: tuple[int, int, int],
    dose: Dose,
    maintenant: datetime,
    presentes: Mapping[str, date],
    jokers: Collection[str],
    aujourdhui: Selection,
) -> str | None:
    """La notion nouvelle du ticket de demain, réservée dès aujourd'hui (#126) : la même
    sélection le lendemain à la même heure locale, la notion du jour comptée comme présentée.
    Sans reprise : une pause ne se prévoit pas ; si elle arrive, la promesse est reportée
    (`quotidien.preparer_jour`)."""
    local = maintenant.astimezone(ZoneInfo(fuseau))
    demain = datetime.combine(aujourdhui.jour + timedelta(days=1), local.time(), ZoneInfo(fuseau))
    vues = dict(presentes)
    if aujourdhui.nouvelle:
        vues.setdefault(aujourdhui.nouvelle.concept_id, aujourdhui.jour)
    suite = selectionner(
        bib, etats, revues, inscriptions, brainiac_id, fuseau, dosage,
        replace(dose, reprise_jours=10**6), demain, vues, jokers,
    )  # fmt: skip
    return suite.nouvelle.concept_id if suite.nouvelle else None
