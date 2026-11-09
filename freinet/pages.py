"""Les pages de lecture servies par la page du QR (décision A12) : `/cours` (les cartes),
`/cours/<carte>` (notions dans l'ordre de la carte, quêtes) et `/fiche/<concept>` (la fiche
complète). Ouvertes sur le réseau de la maison, sans jeton : elles ne montrent que la
bibliothèque (le concept est partagé, B15), jamais l'état d'un élève. Tout texte est échappé ;
une source ne devient un lien que si c'est une URL http(s) admise par le registre (#47).

`document()` et `STYLE` servent à toutes les pages du serveur ; l'espace d'un ticket est
dans `espace.py`. Les libellés viennent de `libelles_espace.py` : français hors espace, langue
du plan dans l'espace (PROF-12).
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urlsplit

from freinet.bibliotheque import Bibliotheque
from freinet.libelles_espace import ESPACE_FR, LibellesEspace
from freinet.sources import Registre, refus

STYLE = Path(__file__).with_name("pages.css").read_text(encoding="utf-8")
_ID = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_ROUTE = re.compile(rf"^/(?:cours/?|cours/(?P<carte>{_ID})/?|fiche/(?P<concept>{_ID})/?)?$")


class PageInconnue(LookupError):
    """Carte ou fiche absente de la bibliothèque, ou chemin qui n'est pas une page de cours."""


def document(
    titre: str, corps: str, espace: str = "", onglets: str = "", langue: str = "fr"
) -> bytes:
    """La page complète. Hors espace, la tête mène aux cours et à la saisie du code ; dans
    l'espace d'un ticket (`espace` = `/r/<jeton>` ou `/k/<code>`), la marque ramène au ticket
    et `onglets` suit la page. `langue` : l'attribut `lang` (celle du plan dans l'espace)."""
    if espace:
        tete = f"<a class='marque' href='{_e(espace)}'>Freinet</a>"
    else:
        tete = (
            "<a class='marque' href='/cours'>Freinet</a>"
            "<nav><a href='/c'>Mon ticket</a><a href='/cours'>Tous les cours</a></nav>"
        )
    return (
        f"<!doctype html><html lang='{_e(langue)}'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
        f"<title>{_e(titre)}</title><style>{STYLE}</style>"
        f"<body{' class=espace' if espace else ''}><main class='feuille'>"
        f"<header class='tete'>{tete}</header>{corps}</main>{onglets}</body></html>"
    ).encode()


def est_page_de_cours(chemin: str) -> bool:
    return _ROUTE.match(chemin) is not None


def page_de_cours(
    chemin: str,
    bib: Bibliotheque,
    registre: Registre,
    prefixe: str = "",
    lib: LibellesEspace = ESPACE_FR,
) -> tuple[str, str]:
    """(titre, corps HTML) de la page ; `PageInconnue` si rien ne correspond. `prefixe`
    précède chaque lien interne (l'espace d'un ticket), vide pour les pages ouvertes."""
    trouve = _ROUTE.match(chemin)
    if trouve is None:
        raise PageInconnue(chemin)
    if trouve["concept"]:
        return _fiche(bib, trouve["concept"], registre, prefixe, lib)
    if trouve["carte"]:
        return _carte(bib, trouve["carte"], prefixe, lib)
    return _sommaire(bib, prefixe, lib)


def _e(texte: str) -> str:
    return html.escape(texte, quote=True)


def paragraphes(texte: str) -> str:
    return "".join(f"<p>{_e(b.strip())}</p>" for b in re.split(r"\n\s*\n", texte) if b.strip())


def lien_fiche(bib: Bibliotheque, concept_id: str, prefixe: str) -> str:
    concept = bib.concepts.get(bib.canonique(concept_id))
    titre = concept.titre if concept else concept_id
    return f"<a href='{_e(prefixe)}/fiche/{_e(concept_id)}'>{_e(titre)}</a>"


def source_html(reference: str, titre: str, domaine: str, registre: Registre) -> str:
    """Un lien (nouvel onglet, sans référent) si l'URL est http(s) et admise par le registre ;
    sinon du texte : un ouvrage, ou une URL que le registre n'admet plus."""
    morceaux = urlsplit(reference)
    if morceaux.scheme in ("http", "https") and refus(reference, domaine, registre) is None:
        texte = titre or morceaux.hostname or reference
        return (
            f"<a href='{_e(reference)}' target='_blank' rel='noopener noreferrer'>{_e(texte)}</a>"
        )
    return _e(f"{titre} — {reference}" if titre else reference)


def lien_carte(carte_id: str, nom: str, prefixe: str) -> str:
    return f"<a href='{_e(prefixe)}/cours/{_e(carte_id)}'>{_e(nom)}</a>"


def _sommaire(bib: Bibliotheque, prefixe: str, lib: LibellesEspace) -> tuple[str, str]:
    cartes = sorted(bib.cartes.values(), key=lambda c: c.id)
    lignes = "".join(
        f"<li><a href='{_e(prefixe)}/cours/{_e(c.id)}'><span>{_e(c.nom)}</span>"
        f"<span class='meta'>{len(c.concepts)} {lib.notions}</span></a></li>"
        for c in cartes
    )
    vide = f"<p class='vide'>{lib.aucune_carte}</p>"
    corps = f"<p class='surtitre'>{lib.bibliotheque}</p><h1>{lib.tous_les_cours}</h1>"
    return lib.tous_les_cours, corps + (f"<ul class='index'>{lignes}</ul>" if lignes else vide)


def _carte(bib: Bibliotheque, carte_id: str, prefixe: str, lib: LibellesEspace) -> tuple[str, str]:
    carte = bib.cartes.get(carte_id)
    if carte is None:
        raise PageInconnue(carte_id)
    notions = "".join(f"<li>{lien_fiche(bib, c, prefixe)}</li>" for c in carte.concepts)
    corps = (
        f"<p class='surtitre'><a href='{_e(prefixe)}/cours'>{lib.cours}</a> · "
        f"{len(carte.concepts)} {lib.notions}</p>"
        f"<h1>{_e(carte.nom)}</h1>"
        f"<h2>{lib.titre_notions}</h2><ol class='notions'>{notions}</ol>"
    )
    quetes = [bib.quetes[q] for q in carte.quetes if q in bib.quetes]
    if quetes:
        lignes = "".join(
            f"<li><b>{_e(q.objectif)}</b><span class='chemin'>"
            f"{' → '.join(lien_fiche(bib, c, prefixe) for c in q.chemin)}</span></li>"
            for q in quetes
        )
        corps += f"<h2>{lib.quetes}</h2><ul class='quetes'>{lignes}</ul>"
    return carte.nom, corps


def _voisines(bib: Bibliotheque, concept_id: str, prefixe: str, lib: LibellesEspace) -> str:
    blocs = []
    for carte in sorted(bib.cartes.values(), key=lambda c: c.id):
        if concept_id not in carte.concepts:
            continue
        lignes = [f"<li class='carte-de'>{lien_carte(carte.id, carte.nom, prefixe)}</li>"]
        avant = [a for a, b in carte.prerequis if b == concept_id]
        apres = [b for a, b in carte.prerequis if a == concept_id]
        if avant:
            liens = ", ".join(lien_fiche(bib, c, prefixe) for c in avant)
            lignes.append(f"<li>{lib.avant}{lib.separateur}{liens}</li>")
        if apres:
            liens = ", ".join(lien_fiche(bib, c, prefixe) for c in apres)
            lignes.append(f"<li>{lib.ensuite}{lib.separateur}{liens}</li>")
        for lien in carte.lateraux:
            if concept_id in (lien.de, lien.vers):
                autre = lien.vers if lien.de == concept_id else lien.de
                nature = lib.natures.get(lien.nature, lien.nature)
                lignes.append(
                    f"<li>{_e(nature)}{lib.separateur}{lien_fiche(bib, autre, prefixe)}</li>"
                )
        blocs.append("".join(lignes))
    if not blocs:
        return ""
    return f"<h2>{lib.voisines}</h2><ul class='voisines'>{''.join(blocs)}</ul>"


def _fiche(
    bib: Bibliotheque, concept_id: str, registre: Registre, prefixe: str, lib: LibellesEspace
) -> tuple[str, str]:
    concept = bib.concepts.get(bib.canonique(concept_id))
    if concept is None:
        raise PageInconnue(concept_id)
    corps = [
        f"<p class='surtitre'>{lib.fiche}"
        f"{' · ' + _e(concept.domaine) if concept.domaine else ''}</p>",
        f"<h1>{_e(concept.titre)}</h1>",
        f"<h2>{lib.lecon}</h2><div class='lecon'>{paragraphes(concept.lecon)}</div>",
    ]
    if concept.version_longue:
        corps.append(f"<h2>{lib.pour_comprendre}</h2>" + paragraphes(concept.version_longue))
    if concept.analogies:
        corps.append(f"<h2>{lib.analogies}</h2>" + paragraphes(concept.analogies))
    if concept.anecdotes:
        lignes = "".join(
            f"<li>{_e(a.texte)}<br><small>{lib.source}{lib.separateur}"
            f"{source_html(a.source, '', concept.domaine, registre)}</small></li>"
            for a in concept.anecdotes
        )
        corps.append(f"<h2>{lib.anecdotes}</h2><ul class='anecdotes'>{lignes}</ul>")
    if concept.sources:
        lignes = "".join(
            f"<li>{source_html(s.reference, s.titre, concept.domaine, registre)}</li>"
            for s in concept.sources
        )
        corps.append(f"<h2>{lib.sources}</h2><ol class='sources'>{lignes}</ol>")
    corps.append(_voisines(bib, concept.id, prefixe, lib))
    return concept.titre, "".join(corps)
