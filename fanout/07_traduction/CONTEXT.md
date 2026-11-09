# 07_traduction — traduire une carte publiée pour un élève d'une autre langue

One job : Fan-out : un agent par concept de la carte ; chaque fichier français publié a son jumeau traduit, même identifiant, même structure.

## Inputs
- Working : `../../bibliotheque/cartes/<carte>.md` · `../../bibliotheque/concepts/<id>.md` · `../../bibliotheque/questions/<id>/` · `../../bibliotheque/quetes/` (la carte publiée, en français)
- Reference : `../../_config/pedagogie.md` · `../../_config/schema-fichiers.md` · `../../freinet/langue.py` (avertissement finance et « Remember: » de la langue)

Do NOT load : les autres étapes, `brainiacs/*/profil/`, les pages web (une traduction n'ajoute aucun fait). Retraduire un fichier = partir de la version française publiée, jamais de l'ancienne traduction.

## Process
1. Un agent par concept (en parallèle) : copie exacte du frontmatter structurel (`id`, `domaine`, `alias`, `origine`, `projet`, `sources` gardent leurs références) ; traduit `titre`, `## Leçon` (≤ 400 caractères, problème d'ouverture, finit par « Remember: … »), `## Version longue`, `## Analogies`, le texte des anecdotes ; puis chaque question du concept (`enonce`, `reponse`, `explication` ; `nature` et `difficulte` inchangées).
2. Un agent pour la carte (`titre` seulement) et ses quêtes (`objectif` seulement).
3. Anglais simple et direct, tutoiement rendu par « you » ; chiffres, devises et exemples inchangés ; finance : la phrase « Educational, not investment advice. » (inv. 9) ; aucun lien dans le texte (#45).
4. `uv run python -m freinet.publication --verifier` doit passer avant de rendre la main.

## Outputs
- `en/concepts/<id>.md` · `en/questions/<concept>/<id>.md` · `en/quetes/<id>.md` · `en/cartes/<id>.md` → output/

## Human check
Lire trois leçons traduites au hasard à voix haute : naturelles, ≤ 400 caractères, « Remember: » à la fin.
