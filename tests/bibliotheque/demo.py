"""La bibliothèque de démonstration (tests/donnees/bibliotheque) et une copie modifiable."""

from __future__ import annotations

import shutil
from pathlib import Path

from freinet.contenu import lire_question

DEMO = Path(__file__).resolve().parents[1] / "donnees" / "bibliotheque"


def copie_demo(destination: Path) -> Path:
    racine = destination / "bibliotheque"
    shutil.copytree(DEMO, racine)
    return racine


def ecrire(chemin: Path, texte: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")


def surcouche_en(racine: Path) -> Path:
    """Traduit en anglais `intervalle` (concept + deux questions) et le titre de la carte."""
    en = racine / "en"
    ecrire(
        en / "concepts" / "intervalle.md",
        "---\ntype: concept\nid: intervalle\ntitre: Interval\ndomaine: musique\n"
        "alias: [intervalles]\n---\n\n## Leçon\n\nThe distance between two notes, counted in "
        "steps: from C to E, a third. Remember: count both ends.\n\n## Version longue\n\n(demo)"
        "\n\n## Analogies\n\nLike the distance between two steps of a staircase.\n",
    )
    for numero, enonce, reponse in ((1, "How many steps in a third?", "Three."),
                                    (2, "Name the interval from C to G.", "A fifth.")):  # fmt: skip
        q = lire_question(DEMO / "questions" / "intervalle" / f"intervalle-q{numero}.md")
        ecrire(
            en / "questions" / "intervalle" / f"intervalle-q{numero}.md",
            f"---\ntype: question\nid: {q.id}\nconcept: intervalle\nnature: {q.nature}\n"
            f'enonce: "{enonce}"\nreponse: "{reponse}"\ndifficulte: {q.difficulte}\n---\n',
        )
    carte = (racine / "cartes" / "harmonie-demo.md").read_text(encoding="utf-8")
    titree = carte.replace("id: harmonie-demo", "id: harmonie-demo\ntitre: Harmony demo", 1)
    ecrire(en / "cartes" / "harmonie-demo.md", titree)
    return en
