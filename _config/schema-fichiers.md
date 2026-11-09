# Schéma des fichiers de la bibliothèque (L3)

> Nommage : **kebab-case** pour tous les fichiers de contenu. Les identifiants sont **immuables** (#20) : un renommage passe par `alias:`.

## Concept — `bibliotheque/concepts/<id>.md`
```yaml
type: concept
id: interets-composes          # global, stable
titre: Intérêts composés
domaine: finance
alias: []
origine: null                  # chemin du COURS_*/rapport si entrée « recherche de projet » (B28)
projet: null                   # ex. ROMAN
sources: [{url: https://..., titre: ...}, {ouvrage: "Auteur, Titre (année)"}]  # un url OU un ouvrage ; titre facultatif
anecdotes: [{texte: ..., source: ...}]
verifie_le: AAAA-MM-JJ
```
Corps : `## Leçon` (≤ 400 car.) · `## Version longue` · `## Analogies`.

## Carte — `bibliotheque/cartes/<id>.md`
```yaml
type: carte
id: gestion-patrimoine
concepts: [...]
prerequis: [[concept_a, concept_b], ...]     # a avant b, sans cycle
lateraux: [{de: x, vers: y, nature: analogie|contraste|meme_idee}]
quetes: [...]
```
`titre` (facultatif) : nom affiché ; sinon l'id, tirets en espaces (PROF-12).

## Quête — `bibliotheque/quetes/<id>.md`
`type: quete` · `id` · `carte` · `objectif` (concret) · `chemin: [concepts]`.

## Question — `bibliotheque/questions/<concept>/<id>.md`
`type: question` · `id` · `concept` · `nature` (voir `pedagogie.md`) · `enonce` · `reponse` · `difficulte` 1-5 · `explication` (facultatif, ≤ 400 caractères : pourquoi cette réponse, l'erreur fréquente ; affichée sur la page du QR après une note de 1 ou 2).
