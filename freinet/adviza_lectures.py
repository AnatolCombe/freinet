"""Les lectures de l'API ADVIZA (contrat v1, PROF-A) : du JSON, jamais du HTML (PRO-9).

Chaque lecture reçoit l'élève du jeton (`Contexte.eleve`) et ne lit que lui : aucune ne prend
d'élève en paramètre (cloisonnement). Rien n'écrit. Le contenu suit la langue du plan du jour,
sinon celle de l'élève dans `general.md` (A13) ; les phrases propres à l'API sont en
français. `brainiacs/<élève>/profil/` n'est jamais lu (inv. 11).

Questions, notion et cartes viennent de la page du QR (`retour.page`, `retour.cartes_de`),
anecdote et défi du plan qui fait foi (`ticket.lire_ticket`). `profil` est un résumé autorisé.
Pas de rattrapage : `a_faire` ne parle que du jour (#103, inv. 15).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from freinet.base import Base
from freinet.base.plans import PlanAcces
from freinet.bibliotheque import Bibliotheque, charger
from freinet.frontmatter import ErreurContenu, lire
from freinet.general import DOSSIER_GENERAL, Profil, lire_config
from freinet.langue import libelles
from freinet.modele import Brainiac
from freinet.retour import (
    OBJECTIF_SEMAINE,
    NotionDeCarte,
    QuestionANoter,
    RetourRefuse,
    cartes_de,
    langue_du_ticket,
    page,
    verifier_delai,
)
from freinet.sources import Registre, lire_registre, refus
from freinet.temps import date_logique, vers_iso
from freinet.ticket import Ticket, lire_ticket, source_anecdote

CONTRAT = "1"
Json = dict[str, object]
ETATS = ("acquis", "en_cours", "debloque", "verrouille")


INCONNU, HORS_FENETRE, SANS_PLAN = "concept inconnu", "jour hors fenêtre", "aucun plan ce jour"


class Introuvable(LookupError):
    """Rien à lire à cette adresse : 404, au motif fixe porté par l'exception."""


@dataclass(frozen=True)
class Contexte:
    racine: Path
    eleve: Brainiac
    instant: datetime
    dossier_general: Path = DOSSIER_GENERAL

    @property
    def jour(self) -> date:
        return date_logique(self.instant, self.eleve.fuseau)


def entete(ctx: Contexte) -> Json:
    return {"contrat": CONTRAT, "releve_le": vers_iso(ctx.instant)}


def general(ctx: Contexte) -> Profil:
    """Prénom et langue (`general.md`) ; une config illisible n'empêche pas de lire."""
    try:
        return lire_config(ctx.dossier_general / "general.md").profil(ctx.eleve.nom)
    except (ErreurContenu, OSError):
        return Profil(ctx.eleve.nom.upper())


def lire_jour(
    base: Base, ctx: Contexte, jour: date | None = None
) -> tuple[PlanAcces | None, str, Bibliotheque]:
    """Le plan du jour visé (le jour courant par défaut), s'il existe, sa langue et la
    bibliothèque dans cette langue."""
    plan = base.plan_de(ctx.eleve.brainiac_id, ctx.jour if jour is None else jour)
    langue = langue_du_ticket(base, ctx.racine, plan) if plan else general(ctx).langue
    return plan, langue, charger(ctx.racine / "bibliotheque", langue)


def bibliotheque_sure(base: Base, ctx: Contexte) -> tuple[str, Bibliotheque]:
    """La langue du plan du jour et sa bibliothèque ; plan absent ou illisible, celle de
    `general.md` : une fiche ou une carte ne dépend pas du ticket du jour."""
    plan = base.plan_de(ctx.eleve.brainiac_id, ctx.jour)
    try:
        langue = langue_du_ticket(base, ctx.racine, plan) if plan else general(ctx).langue
    except (RetourRefuse, ErreurContenu, OSError):
        langue = general(ctx).langue
    return langue, charger(ctx.racine / "bibliotheque", langue)


def _maitrise(bib: Bibliotheque, carte_id: str, notions: tuple[NotionDeCarte, ...]) -> Json:
    compte: Json = {"carte": carte_id, "nom": bib.cartes[carte_id].nom, "total": len(notions)}
    return compte | {e: sum(1 for n in notions if n.etat == e) for e in ETATS}


def _profil(base: Base, ctx: Contexte, bib: Bibliotheque) -> Json:
    profil, etats = general(ctx), base.etat(ctx.eleve.brainiac_id)
    inscrites: list[Json] = [
        {
            "id": i.carte_id,
            "nom": bib.cartes[i.carte_id].nom if i.carte_id in bib.cartes else i.carte_id,
            "quete": i.quete_active,
        }
        for i in base.inscriptions(ctx.eleve.brainiac_id)
    ]
    return {
        "nom": ctx.eleve.nom,
        "prenom": profil.prenom,
        "langue": profil.langue,
        "fuseau": ctx.eleve.fuseau,
        "cartes": inscrites,
        "concepts_acquis": sum(1 for e in etats if e.acquis_le is not None),
        "concepts_en_cours": sum(1 for e in etats if e.acquis_le is None),
    }


def etat(base: Base, ctx: Contexte) -> Json:
    """`GET /adviza/etat` : jauges, choses à faire du jour, profil résumé."""
    plan, langue, bib = lire_jour(base, ctx)
    ticket: Json | None = None
    notion: Json | None = None
    a_faire: list[Json] = []
    if plan is not None:
        p = page(base, bib, ctx.racine, plan, langue)
        jour, notees = plan.jour.isoformat(), sum(1 for q in p.questions if q.note is not None)
        ticket = {
            "jour": jour,
            "statut": base.statut_du_plan(plan.brainiac_id, plan.jour),
            "questions": len(p.questions),
            "notees": notees,
            "joker": p.joker,
        }
        if p.nouvelle_id:
            notion = {"id": p.nouvelle_id, "titre": p.nouvelle}
        if len(p.questions) > notees:
            titre = f"Ticket du jour : {len(p.questions) - notees} question(s) à noter"
            a_faire.append({"id": f"ticket:{jour}", "titre": titre, "echeance": jour})
        if p.nouvelle_id:  # une entrée par jour et par notion, le jour même (#103, inv. 14)
            titre = f"À découvrir : {p.nouvelle}"
            a_faire.append(
                {"id": f"notion:{jour}:{p.nouvelle_id}", "titre": titre, "echeance": jour}
            )
        if p.demain:
            titre = f"À lire pour demain : {p.demain[1]}"
            a_faire.append({"id": f"demain:{jour}:{p.demain[0]}", "titre": titre, "echeance": jour})
    lundi = ctx.jour - timedelta(days=ctx.jour.weekday())
    semaine = base.tickets_notes(ctx.eleve.brainiac_id, lundi, lundi + timedelta(days=6))
    par_carte = cartes_de(base, bib, ctx.eleve.brainiac_id, ctx.jour)
    jauges: Json = {
        "ticket": ticket,
        "notion_du_jour": notion,
        "semaine": {"notes": semaine, "objectif": OBJECTIF_SEMAINE},
        "maitrise": [_maitrise(bib, carte_id, notions) for carte_id, notions in par_carte],
    }
    return entete(ctx) | {"jauges": jauges, "a_faire": a_faire, "profil": _profil(base, ctx, bib)}


def _extraits(ticket: Ticket) -> tuple[str | None, str | None, str | None]:
    """(anecdote, défi, avertissement finance) tels que le ticket les imprime (inv. 9)."""
    lib = ticket.libelles
    textes: dict[str, str] = {}
    section, avertissement = "", None
    for bloc in ticket.blocs:
        if bloc.genre == "titre":
            section = bloc.texte
        elif bloc.genre == "texte" and section not in textes:
            textes[section] = bloc.texte
        elif bloc.genre == "avertissement":
            avertissement = bloc.texte
    return textes.get(lib.anecdote), textes.get(lib.defi), avertissement


def _revision(bib: Bibliotheque, q: QuestionANoter) -> Json:
    concept_de = bib.concepts.get(bib.canonique(q.concept_id))
    return {
        "question_id": q.question_id,
        "concept_id": q.concept_id,
        "concept": concept_de.titre if concept_de else q.concept_id,
        "nature": q.nature,
        "enonce": q.enonce,
        "reponse": q.reponse,
        "explication": q.explication,
        "retiens": q.retiens,
        "note": q.note,
    }


def aujourdhui(base: Base, ctx: Contexte, jour: date | None = None) -> Json:
    """`GET /adviza/aujourdhui` : le plan du jour ; `plan: null` avant le ticket du matin.
    `/aujourdhui/<AAAA-MM-JJ>` (PROF-A4) : celui d'un jour de la fenêtre du QR
    (`retour.verifier_delai`), 404 hors fenêtre ou sans plan. Une lecture seulement :
    `etat.a_faire` reste au jour courant (#103)."""
    if jour is not None:
        try:
            verifier_delai(jour, ctx.jour)
        except RetourRefuse:
            raise Introuvable(HORS_FENETRE) from None
    plan, langue, bib = lire_jour(base, ctx, jour)
    vise = ctx.jour if jour is None else jour
    corps = entete(ctx) | {"jour": vise.isoformat(), "langue": langue}
    if plan is None:
        if jour is not None:
            raise Introuvable(SANS_PLAN)
        return corps | {"plan": None}
    p = page(base, bib, ctx.racine, plan, langue)
    chemin = ctx.racine / "brainiacs" / ctx.eleve.nom / "plans" / f"{plan.jour.isoformat()}.md"
    entete_du_plan, _ = lire(chemin)
    anecdote, defi, avertissement = _extraits(lire_ticket(chemin, bib))
    nouvelle = bib.concepts.get(bib.canonique(p.nouvelle_id)) if p.nouvelle_id else None
    contenu: Json = {
        "statut": base.statut_du_plan(plan.brainiac_id, plan.jour),
        "joker": p.joker,
        "anecdote": (
            {"texte": anecdote, "source": source_anecdote(entete_du_plan)} if anecdote else None
        ),
        "revisions": [_revision(bib, q) for q in p.questions],
        "nouvelle": (
            {"id": nouvelle.id, "titre": nouvelle.titre, "lecon": nouvelle.lecon}
            if nouvelle
            else None
        ),
        "demain": {"id": p.demain[0], "titre": p.demain[1]} if p.demain else None,
        "defi": defi,
        "avertissement": avertissement,
    }
    return corps | {"plan": contenu}


def cartes(base: Base, ctx: Contexte) -> Json:
    """`GET /adviza/cartes` : chaque carte de l'élève, sa quête, l'état de chaque notion."""
    langue, bib = bibliotheque_sure(base, ctx)
    quetes = {i.carte_id: i.quete_active for i in base.inscriptions(ctx.eleve.brainiac_id)}
    rendu: list[Json] = []
    for carte_id, notions in cartes_de(base, bib, ctx.eleve.brainiac_id, ctx.jour):
        quete = bib.quetes.get(quetes.get(carte_id) or "")
        rendu.append(
            {
                "id": carte_id,
                "nom": bib.cartes[carte_id].nom,
                "quete": {"id": quete.id, "objectif": quete.objectif} if quete else None,
                "notions": [
                    {"id": n.concept_id, "titre": n.titre, "etat": n.etat} for n in notions
                ],
            }
        )
    return entete(ctx) | {"langue": langue, "cartes": rendu}


def _source(reference: str, titre: str, domaine: str, registre: Registre) -> Json:
    """Un lien seulement si le registre de confiance l'admet (#45, comme `pages.source_html`)."""
    web = reference.startswith(("http://", "https://"))
    lien = web and refus(reference, domaine, registre) is None
    return {"reference": reference, "titre": titre, "lien": lien}


def concept(base: Base, ctx: Contexte, concept_id: str) -> Json:
    """`GET /adviza/concept/<id>` : la fiche d'un concept ; un alias mène à son id actuel."""
    langue, bib = bibliotheque_sure(base, ctx)
    trouve = bib.concepts.get(bib.canonique(concept_id))
    if trouve is None:
        raise Introuvable(INCONNU)
    registre, domaine = lire_registre(), trouve.domaine
    finance = libelles(langue).avertissement_finance.capitalize() + "."  # inv. 9, B26
    return entete(ctx) | {
        "langue": langue,
        "id": trouve.id,
        "titre": trouve.titre,
        "domaine": domaine,
        "lecon": trouve.lecon,
        "version_longue": trouve.version_longue,
        "analogies": trouve.analogies,
        "anecdotes": [
            {"texte": a.texte, "source": _source(a.source, "", domaine, registre)}
            for a in trouve.anecdotes
        ],
        "sources": [_source(s.reference, s.titre, domaine, registre) for s in trouve.sources],
        "avertissement": finance if domaine == "finance" else None,
    }


def catalogue(base: Base, ctx: Contexte) -> Json:
    """`GET /adviza/catalogue` : les cartes publiées, celles où l'élève est inscrit et sa quête."""
    langue = general(ctx).langue  # celle de l'élève (A13), sans dépendre du ticket du jour
    bib = charger(ctx.racine / "bibliotheque", langue)
    inscrites = {i.carte_id: i.quete_active for i in base.inscriptions(ctx.eleve.brainiac_id)}
    cartes: list[Json] = [
        {
            "id": c.id,
            "nom": c.nom,
            "concepts": len(c.concepts),
            "quetes": [
                {"id": q, "objectif": bib.quetes[q].objectif} for q in c.quetes if q in bib.quetes
            ],
            "inscrite": c.id in inscrites,
            "quete_active": inscrites.get(c.id),
        }
        for c in sorted(bib.cartes.values(), key=lambda c: c.id)
    ]
    return entete(ctx) | {"langue": langue, "cartes": cartes}
