"""L'espace d'un ticket : tout ce qui suit `/r/<jeton>` ou `/k/<code>` (spec 2026-09-30,
espace du ticket). Trois onglets : Aujourd'hui (le ticket à noter), Ma carte (l'état de chaque
notion), Cours (la bibliothèque de `pages.py`, liens préfixés par l'espace). Aucun lien n'en
sort. Privé : on n'y entre qu'avec le jeton ou le code du ticket (`serveur.py`). Les libellés
suivent la langue du plan (`libelles_espace.py`, PROF-12).
"""

from __future__ import annotations

from datetime import date
from html import escape as _e

from freinet.contenu import nom_par_defaut
from freinet.langue import libelles
from freinet.libelles_espace import ESPACE_FR, LibellesEspace
from freinet.pages import document, lien_carte, paragraphes
from freinet.retour import Page, QuestionANoter

SUFFIXES = ("", "/carte", "/cours")  # Aujourd'hui · Ma carte · Cours


def jour_lisible(jour: date, lib: LibellesEspace = ESPACE_FR) -> str:
    texte = libelles(lib.code).date_longue(jour)
    return texte[:1].upper() + texte[1:]


def barre(espace: str, actif: str, lib: LibellesEspace = ESPACE_FR) -> str:
    """La barre d'onglets ; `actif` est le suffixe de l'onglet courant : `""`, `/carte`,
    `/cours`."""
    liens = []
    for suffixe, nom in zip(SUFFIXES, lib.onglets, strict=True):
        courant = " aria-current='page'" if suffixe == actif else ""
        liens.append(f"<a href='{_e(espace + suffixe)}'{courant}>{_e(nom)}</a>")
    return f"<nav class='onglets'>{''.join(liens)}</nav>"


def page_de_lecture(titre: str, corps: str, espace: str, lib: LibellesEspace = ESPACE_FR) -> bytes:
    """Une page de la bibliothèque (`pages.page_de_cours` avec le préfixe) dans l'espace."""
    return document(titre, corps, espace, barre(espace, "/cours", lib), lib.code)


def _fiche(espace: str, concept_id: str) -> str:
    return f"{_e(espace)}/fiche/{_e(concept_id)}"


def page_du_jour(p: Page, espace: str, lib: LibellesEspace = ESPACE_FR) -> bytes:
    """Aujourd'hui : à lire pour demain, notion du jour, semaine, questions, joker."""
    morceaux = [
        f"<p class='surtitre'>{lib.ticket_du_matin}</p><h1>{_e(jour_lisible(p.jour, lib))}</h1>"
    ]
    if p.demain:
        concept_id, titre_demain = p.demain
        morceaux.append(
            f"<p class='encart'>{lib.a_lire_demain}{lib.separateur}"
            f"<a href='{_fiche(espace, concept_id)}'>{_e(titre_demain)}</a></p>"
        )
    if p.nouvelle_id:
        titre = p.nouvelle or p.nouvelle_id
        morceaux.append(
            f"<p class='du-jour'>{lib.notion_du_jour}{lib.separateur}"
            f"<a href='{_fiche(espace, p.nouvelle_id)}'>{_e(titre)}</a></p>"
        )
    notes, objectif = p.semaine
    points = "".join(
        f"<i{' class=plein' if n < notes else ''}></i>" for n in range(max(notes, objectif))
    )
    morceaux.append(
        f"<p class='semaine'><span class='points' aria-hidden='true'>{points}</span>"
        f"<span>{lib.semaine.format(notes=notes, objectif=objectif)}</span></p>"
    )
    if p.cartes:
        morceaux.append(f"<p class='info'><a href='{_e(espace)}/carte'>{lib.voir_ma_carte}</a></p>")
    morceaux.append(f"<h2>{lib.questions}</h2>")
    if not p.questions:
        morceaux.append(f"<p class='vide'>{lib.rien_a_noter}</p>")
    for n, q in enumerate(p.questions, 1):
        morceaux.append(_question(n, q, espace, lib))
    if p.nouvelle:
        if p.joker:
            morceaux.append(f"<p class='info'>{lib.joker_note.format(titre=_e(p.nouvelle))}</p>")
        else:
            morceaux.append(
                f"<form class='joker' method='post' action='{_e(espace)}/joker'><button>"
                f"{lib.joker_bouton.format(titre=_e(p.nouvelle))}</button></form>"
            )
    titre_page = lib.titre_du_jour.format(jour=p.jour.isoformat())
    return document(titre_page, "".join(morceaux), espace, barre(espace, "", lib), lib.code)


def _question(n: int, q: QuestionANoter, espace: str, lib: LibellesEspace) -> str:
    fiche = _fiche(espace, q.concept_id)
    boutons = "".join(
        f"<button name='note' value='{v}'{' class=choisie' if q.note == v else ''}>"
        f"{v} · {_e(libelle)}</button>"
        for v, libelle in lib.notes.items()
    )
    reponse = (
        f"<details><summary>{lib.voir_reponse}</summary><p>{_e(q.reponse)}</p></details>"
        if q.reponse
        else ""
    )
    revoir = (
        f"<details class='revoir'><summary>{lib.revoir_lecon}</summary>{paragraphes(q.lecon)}"
        f"<p class='suite'><a href='{fiche}'>{lib.fiche_complete}</a></p></details>"
        if q.lecon
        else ""
    )
    aide = ""
    if q.note in (1, 2):
        if q.explication:
            aide = f"<p class='aide'>{_e(q.explication)}</p>"
        else:
            aide = f"<p class='aide'>{_e(q.retiens)} <a href='{fiche}'>{lib.relire_fiche}</a></p>"
    return (
        f"<div class='q'><p class='enonce'><b class='num'>{lib.question.format(n=n)}</b>"
        f"{_e(q.enonce)}</p>"
        f"{reponse}{revoir}<form class='notes' method='post' action='{_e(espace)}/note'>"
        f"<input type='hidden' name='question' value='{_e(q.question_id)}'>"
        f"{boutons}</form>{aide}</div>"
    )


def page_ma_carte(p: Page, espace: str, lib: LibellesEspace = ESPACE_FR) -> bytes:
    """Ma carte : chaque carte suivie, ses notions dans l'ordre et leur état."""
    noms = dict(p.noms_de_cartes)
    blocs = []
    for carte_id, notions in p.cartes:
        lignes = "".join(
            f"<li><a href='{_fiche(espace, n.concept_id)}'>{_e(n.titre)}</a>"
            f"<span class='etat etat-{_e(n.etat)}'>{_e(lib.etats.get(n.etat, n.etat))}</span>"
            "</li>"
            for n in notions
        )
        nom = noms.get(carte_id, nom_par_defaut(carte_id))
        blocs.append(
            f"<h2>{lien_carte(carte_id, nom, espace)}</h2><ol class='notions'>{lignes}</ol>"
        )
    entete = f"<p class='surtitre'>{lib.ma_carte}</p><h1>{lib.ou_j_en_suis}</h1>"
    corps = entete + ("".join(blocs) or f"<p class='vide'>{lib.aucune_carte_suivie}</p>")
    return document(lib.ma_carte, corps, espace, barre(espace, "/carte", lib), lib.code)
