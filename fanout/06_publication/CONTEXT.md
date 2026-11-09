# 06_publication — valider puis publier, sans LLM

One job : Script seul : valider, échanger dans `bibliotheque/`, régénérer l'index, archiver le run. L'opérateur committe.

## Inputs
- Working : `../02_carte/output/` · `../03_redaction/output/` · `../04_questions/output/`
- Reference : `../../_config/schema-fichiers.md`

Do NOT load : les `output/` d'autres runs, les autres étapes, `brainiacs/*/profil/`.

## Commande
`.venv/bin/python -m freinet.publication` (options `--fanout`, `--bibliotheque`, `--base data/freinet.db`, `--verifier`) : code 0 = publié et sorties archivées dans `fanout/_publies/`, 1 = refusé, rien n'a bougé. Un renommage réémet aussi la carte, les quêtes et les questions sous le nouvel id.

## Process
1. Construire un arbre de préparation (bibliothèque actuelle + nouveaux fichiers) et le revalider en entier : frontmatter, cycles, orphelins, identifiants, sources, avertissement finance (inv. 8, 9).
2. Refuser la disparition d'un **concept** déjà référencé par `revue` (#20). Un renommage passe par `alias: [ancien]` : la publication retire alors `ancien` et ses questions. Sinon la bibliothèque est cumulative : un fichier absent du fan-out reste en place.
3. Échanger l'arbre validé avec `bibliotheque/` (renommages, retour arrière si un échec), régénérer `index.md`. L'opérateur committe ensuite `bibliotheque/`. La recherche FTS5 n'a pas de table à régénérer : elle est reconstruite en mémoire à chaque appel.

## Outputs
- `publication.md` (compte rendu) → output/ ; contenu → `../../bibliotheque/`

## Human check
Lire le compte rendu : nombre de concepts créés, réutilisés, enrichis. Code de sortie ≠ 0 = rien n'a été publié.
