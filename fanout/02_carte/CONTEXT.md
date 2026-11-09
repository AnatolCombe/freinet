# 02_carte — dessiner la carte de concepts

One job : Transformer le cadrage en graphe : concepts, prérequis, liens latéraux, chemins de quêtes.

## Inputs
- Working : `../01_cadrage/output/cadrage.md`
- Reference : `../../_config/schema-fichiers.md` · `../../bibliotheque/index.md` (+ recherche FTS5 des concepts existants, #43)

Do NOT load : les `output/` d'autres runs, les autres étapes, `brainiacs/*/profil/`.

## Process
1. Pour chaque concept candidat : `.venv/bin/python -m freinet.recherche "<titre>" --domaine <d>` rend les 5 concepts existants les plus proches — **réutiliser** plutôt que créer.
2. Homonyme inter-domaines (`levier` trading ≠ patrimoine) : signaler, ne pas fusionner (#43).
3. Écrire prérequis (sans cycle) et liens latéraux typés.
4. Script de validation : cycles, orphelins, identifiants invalides → refus.

## Outputs
- `cartes/<id>.md` · `quetes/<id>.md` (schéma `_config/schema-fichiers.md`) → output/
- `carte.mmd` : rendu Mermaid pour la gate (`freinet.mermaid.mermaid`, #5) → output/

## Human check
**Gate lourde** : lire le Mermaid, vérifier l'ordre des prérequis et chaque réutilisation de concept existant.
