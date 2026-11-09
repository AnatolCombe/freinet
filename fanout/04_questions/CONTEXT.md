# 04_questions — écrire les questions typées

One job : 4 à 6 questions par concept, dont au moins une de transfert.

## Inputs
- Working : `../03_redaction/output/concepts/` · `../00_import/output/source.md` si entrée « recherche de projet » (ancrage projet → transfert)
- Reference : `../../_config/pedagogie.md` · `../../_config/schema-fichiers.md`

Do NOT load : les `output/` d'autres runs, les autres étapes (hors les Inputs ci-dessus), `brainiacs/*/profil/`. Concept déjà publié : numéroter après ses questions existantes (`bibliotheque/questions/<concept>/`), sinon elles sont écrasées.

## Process
1. Un agent par concept.
2. Types : rappel, application, transfert (≥ 1), piège, amorce Feynman, pré-test.
3. Pour une entrée « recherche de projet » : les questions de transfert s'appuient sur l'ancrage projet.
4. Chaque question reçoit son `explication` (`_config/pedagogie.md`) : écrite pour quelqu'un qui vient de se tromper, elle ne répète pas la réponse, elle dit pourquoi.

## Outputs
- `questions/<concept>/<concept>-qN.md` (nom de fichier = id) → output/

## Human check
Vérifier que chaque concept a sa question de transfert et qu'aucune réponse n'est ambiguë.
