# 05_verification — attaquer le contenu avant publication

One job : Critique adverse : faits, sources, clarté, grille pédagogique.

## Inputs
- Working : `../03_redaction/output/` · `../04_questions/output/`
- Reference : `../../_config/sources/` · `../../_config/pedagogie.md` (grille LearnLM)

Do NOT load : les `output/` d'autres runs, les autres étapes, `brainiacs/*/profil/`.

## Process
0. Contrôle mécanique d'abord : `.venv/bin/python -m freinet.publication --verifier` liste tout défaut de forme (domaine, leçon > 400, analogie, liens ou balisage, sources hors registre, finance, questions) **sans rien publier** ni lire la base.
1. Chaque fait et chaque anecdote contre sa source, domaine au registre obligatoire (#47) ; chaque **ouvrage** cité est vérifié ici à la main (le script ne sait qu'en contrôler la forme).
2. Élève simulé : relit comme un débutant, signale ce qui ne passe pas.
3. Grille LearnLM (#59), par concept : apprentissage actif et difficulté utile · charge cognitive · adaptation à l'élève · curiosité · métacognition — une alerte par principe manqué.
4. Finance : avertissement présent (inv. 9).

## Outputs
- `alertes.md` → output/

## Human check
**Gate lourde** : traiter chaque alerte (corriger dans `03`/`04` ou accepter en le disant).
