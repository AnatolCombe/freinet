"""`bibliotheque/index.md` est GÉNÉRÉ (inv. 13) : même bibliothèque → même octets."""

from __future__ import annotations

from freinet.bibliotheque import Bibliotheque

EN_TETE = "<!-- GÉNÉRÉ par fanout/06_publication — ne pas modifier à la main (inv. 13) -->\n"


def _cellule(texte: str) -> str:
    """Une cellule de tableau Markdown : ni `|` ni retour à la ligne ne cassent la ligne."""
    return texte.replace("|", "\\|").replace("\n", " ")


def generer_index(bib: Bibliotheque) -> str:
    lignes = [EN_TETE.rstrip("\n"), "# Index de la bibliothèque", ""]
    if not bib.cartes:
        lignes.append("Vide : aucune carte publiée.")
        return "\n".join(lignes) + "\n"
    lignes += ["## Cartes", "", "| Carte | Concepts | Quêtes |", "|---|---|---|"]
    for carte in sorted(bib.cartes.values(), key=lambda c: c.id):
        quetes = ", ".join(sorted(carte.quetes)) or "—"
        lignes.append(f"| {carte.id} | {len(carte.concepts)} | {quetes} |")
    cartes_de: dict[str, list[str]] = {}
    for carte in bib.cartes.values():
        for id_concept in carte.concepts:
            cartes_de.setdefault(id_concept, []).append(carte.id)
    lignes += ["", "## Concepts", "", "| Concept | Titre | Domaine | Cartes |", "|---|---|---|---|"]
    for concept in sorted(bib.concepts.values(), key=lambda c: c.id):
        cartes = ", ".join(sorted(cartes_de.get(concept.id, []))) or "—"
        titre, domaine = _cellule(concept.titre), _cellule(concept.domaine)
        lignes.append(f"| {concept.id} | {titre} | {domaine} | {cartes} |")
    return "\n".join(lignes) + "\n"
