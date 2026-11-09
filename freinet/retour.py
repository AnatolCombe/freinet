"""`quotidien/04_retour` : ce que montre la page du QR, et ce qu'un tap écrit (inv. 3, 15).

Le plan du jour fait foi pour les questions à noter. Une note s'écrit une fois : son
identifiant est dérivé du plan et de la question, donc un double envoi n'ajoute rien ; une
note différente devient une correction (événement compensatoire, `corrige_id`). Le joker « je
sais déjà » (#26) porte sur la notion nouvelle : le lendemain, son premier rappel est une
question de transfert. Un ticket se note jusqu'à `JOURS_VALIDES` jours après son jour.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from freinet.base import Base
from freinet.base.plans import PlanAcces
from freinet.bibliotheque import Bibliotheque
from freinet.frontmatter import lire
from freinet.graphe import etats_maitrise
from freinet.langue import FR, LANGUE_PAR_DEFAUT, Libelles, libelles
from freinet.libelles_espace import libelles_espace
from freinet.modele import Revue
from freinet.rejeu import effectives
from freinet.temps import date_logique
from freinet.ticket import langue_du_plan

NOTES = (1, 2, 3, 4)  # Raté, Difficile, Bien, Facile : libellés dans libelles_espace.py
JOURS_VALIDES = 7
OBJECTIF_SEMAINE = 5  # tickets notés sur 7 (#9) : pas de série à tenir
CANAL = "qr"
ESPACE_IDS = uuid.UUID("0b6d1c0e-5f3a-4c8e-9a41-7d2f6e8b9c10")
ESSAIS = 3


class RetourRefuse(ValueError):
    """Demande impossible à honorer (ticket trop ancien, question hors du plan) : message à
    afficher tel quel sur la page."""


class EnvoiConcurrent(RetourRefuse):
    """Conflit passager : des envois simultanés ont pris tous les essais ; réessayer. La page
    du QR l'affiche comme tout refus ; l'API ADVIZA ne l'enregistre pas (503)."""


@dataclass(frozen=True)
class QuestionANoter:
    question_id: str
    concept_id: str
    nature: str
    enonce: str
    note: int | None
    reponse: str = ""
    explication: str = ""
    retiens: str = ""  # repli de l'explication : la dernière phrase de la leçon
    lecon: str = ""  # la leçon du concept, dépliable sous la question (PROF-11)


@dataclass(frozen=True)
class NotionDeCarte:
    concept_id: str
    titre: str
    etat: str  # acquis · en_cours · debloque · verrouille (`graphe.etats_maitrise`)


@dataclass(frozen=True)
class Page:
    jour: date
    questions: tuple[QuestionANoter, ...]
    nouvelle: str | None  # titre de la notion nouvelle, pour le joker
    joker: bool
    semaine: tuple[int, int]  # (tickets notés cette semaine, objectif)
    nouvelle_id: str | None = None
    cartes: tuple[tuple[str, tuple[NotionDeCarte, ...]], ...] = ()
    demain: tuple[str, str] | None = None  # (concept_id, titre) : la fiche à lire (#126)
    noms_de_cartes: tuple[tuple[str, str], ...] = ()  # (carte_id, nom) dans la langue du plan


@dataclass(frozen=True)
class _Contexte:
    plan: PlanAcces
    nom: str
    fuseau: str
    items: tuple[tuple[str, str, str], ...]  # (question_id, concept_id, nature)
    demain: str | None = None  # la notion annoncée pour demain (#126)


def _chemin_du_plan(racine: Path, nom: str, plan: PlanAcces) -> Path:
    return racine / "brainiacs" / nom / "plans" / f"{plan.jour.isoformat()}.md"


def langue_du_ticket(base: Base, racine: Path, plan: PlanAcces) -> str:
    """La langue du plan de ce ticket (PROF-12) : celle de sa bibliothèque et de ses pages."""
    eleve = base.brainiac(plan.brainiac_id)
    if eleve is None:
        raise RetourRefuse("élève inconnu")
    return langue_du_plan(_chemin_du_plan(racine, eleve.nom, plan))


def _contexte(base: Base, racine: Path, plan: PlanAcces) -> _Contexte:
    eleve = base.brainiac(plan.brainiac_id)
    if eleve is None:
        raise RetourRefuse("élève inconnu")
    entete, _ = lire(_chemin_du_plan(racine, eleve.nom, plan))
    brut = entete.get("items")
    items = tuple(
        (str(i.get("question_id")), str(i.get("concept_id")), str(i.get("nature")))
        for i in (brut if isinstance(brut, list) else [])
        if isinstance(i, dict)
    )
    demain = entete.get("demain")
    return _Contexte(
        plan, eleve.nom, eleve.fuseau, items, demain if isinstance(demain, str) else None
    )


def _revues_du_plan(base: Base, plan: PlanAcces) -> list[Revue]:
    return [r for r in base.revues(plan.brainiac_id) if r.plan_id == plan.plan_id]


def _notes(revues: list[Revue]) -> dict[str, int]:
    return {r.question_id: r.note for r in effectives(revues)}


def retiens(lecon: str, lib: Libelles = FR) -> str:
    """La phrase « Retiens : … » (« Remember: … ») qui clôt la leçon (`_config/pedagogie.md`),
    sinon la leçon."""
    debut = lecon.find(lib.retiens)
    return lecon[debut:].strip() if debut >= 0 else lecon.strip()


def cartes_de(
    base: Base, bib: Bibliotheque, brainiac_id: str, jour: date
) -> tuple[tuple[str, tuple[NotionDeCarte, ...]], ...]:
    """L'état de chaque notion des cartes de l'élève ce jour-là : acquise, en cours (présentée
    ou révisée), débloquée ou à venir. Lu par la page du QR et par l'API ADVIZA."""
    etats = base.etat(brainiac_id)
    acquis = {bib.canonique(e.concept_id) for e in etats if e.acquis_le is not None}
    presentes = base.concepts_presentes(brainiac_id, jour + timedelta(days=1))
    vus = {bib.canonique(e.concept_id) for e in etats} | {bib.canonique(c) for c in presentes}
    rendu = []
    for inscription in base.inscriptions(brainiac_id):
        carte = bib.cartes.get(inscription.carte_id)
        if carte is None:
            continue
        par_concept = etats_maitrise(carte, acquis, vus - acquis)
        notions = tuple(
            NotionDeCarte(c, bib.concepts[c].titre if c in bib.concepts else c, par_concept[c])
            for c in carte.concepts
        )
        rendu.append((carte.id, notions))
    return tuple(rendu)


def verifier_delai(jour: date, aujourdhui: date) -> None:
    """La fenêtre du QR : un ticket se note (et ADVIZA le lit, PROF-A4) de son jour à
    `JOURS_VALIDES` jours après ; `RetourRefuse` sinon."""
    ecart = (aujourdhui - jour).days
    if ecart < 0:
        raise RetourRefuse(f"ticket du {jour.isoformat()} : pas encore arrivé")
    if ecart > JOURS_VALIDES:
        raise RetourRefuse(f"ticket du {jour.isoformat()} : trop ancien pour noter")


def page(
    base: Base,
    bib: Bibliotheque,
    racine: Path,
    plan: PlanAcces,
    langue: str = LANGUE_PAR_DEFAUT,
) -> Page:
    lib, web = libelles(langue), libelles_espace(langue)
    contexte = _contexte(base, racine, plan)
    notes = _notes(_revues_du_plan(base, plan))

    def _question(qid: str, concept_id: str, nature: str) -> QuestionANoter:
        question = bib.questions.get(qid)
        concept_de = bib.concepts.get(bib.canonique(concept_id))
        return QuestionANoter(
            qid,
            concept_id,
            nature,
            question.enonce if question else web.question_retiree,
            notes.get(qid),
            question.reponse if question else "",
            question.explication if question else "",
            retiens(concept_de.lecon, lib) if concept_de else "",
            concept_de.lecon if concept_de else "",
        )

    questions = tuple(_question(*item) for item in contexte.items)
    concept = bib.concepts.get(bib.canonique(plan.nouvelle)) if plan.nouvelle else None
    promis = bib.concepts.get(bib.canonique(contexte.demain)) if contexte.demain else None
    lundi = plan.jour - timedelta(days=plan.jour.weekday())
    semaine = base.tickets_notes(plan.brainiac_id, lundi, lundi + timedelta(days=6))
    cartes = cartes_de(base, bib, plan.brainiac_id, plan.jour)
    return Page(
        plan.jour,
        questions,
        concept.titre if concept else plan.nouvelle,
        plan.joker,
        (semaine, OBJECTIF_SEMAINE),
        concept.id if concept else plan.nouvelle,
        cartes,
        (promis.id, promis.titre) if promis else None,
        tuple((c, bib.cartes[c].nom if c in bib.cartes else c) for c, _ in cartes),
    )


def noter(
    base: Base,
    racine: Path,
    plan: PlanAcces,
    question_id: str,
    note: int,
    instant: datetime,
    canal: str = CANAL,
) -> str:
    """Écrit la note ; rend `notée`, `corrigée` ou `inchangée`. `canal` : `qr` (la page) ou
    `adviza` (l'API, PROF-A3) ; l'identifiant de la revue n'en dépend pas."""
    if note not in NOTES:
        raise RetourRefuse("note invalide (1 à 4)")
    contexte = _contexte(base, racine, plan)
    verifier_delai(plan.jour, date_logique(instant, contexte.fuseau))
    item = next((i for i in contexte.items if i[0] == question_id), None)
    if item is None:
        raise RetourRefuse("cette question n'est pas sur ce ticket")
    _, concept_id, nature = item
    fin_du_jour = datetime.combine(plan.jour + timedelta(days=1), time(), ZoneInfo(contexte.fuseau))
    repondu_le = min(instant, fin_du_jour - timedelta(seconds=1))  # répondu au stylo ce jour-là
    origine = str(uuid.uuid5(ESPACE_IDS, f"{plan.plan_id}/{question_id}"))
    for _ in range(ESSAIS):  # un envoi concurrent peut prendre l'identifiant visé : on relit
        revues = [r for r in _revues_du_plan(base, plan) if r.question_id == question_id]
        if not any(r.revue_id == origine for r in revues):
            revue = Revue(
                origine, plan.brainiac_id, concept_id, question_id, nature, note,
                repondu_le, instant, canal, plan.plan_id,
            )  # fmt: skip
            if base.ajouter_revue_unique(revue):
                base.marquer_note(plan.plan_id)
                return "notée"
            continue
        if _notes(revues).get(question_id) == note:
            return "inchangée"
        rang = sum(1 for r in revues if r.corrige_id is not None) + 1
        correction = Revue(
            str(uuid.uuid5(ESPACE_IDS, f"{origine}/{rang}")), plan.brainiac_id, concept_id,
            question_id, nature, note, repondu_le, instant, canal, plan.plan_id, origine,
        )  # fmt: skip
        if base.ajouter_revue_unique(correction):
            return "corrigée"
    raise EnvoiConcurrent("trop d'envois simultanés : réessayer")


def joker(base: Base, racine: Path, plan: PlanAcces, instant: datetime) -> None:
    """« Je sais déjà » sur la notion nouvelle : vérifié demain par une question de transfert."""
    contexte = _contexte(base, racine, plan)
    verifier_delai(plan.jour, date_logique(instant, contexte.fuseau))
    if plan.nouvelle is None:
        raise RetourRefuse("pas de notion nouvelle sur ce ticket")
    base.marquer_note(plan.plan_id, joker=True)
