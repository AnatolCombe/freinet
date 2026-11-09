# 00_import — transformer un document de projet en source

One job : Un document de projet (cours, rapport) devient la matière d'entrée du cadrage.

## Inputs
- Working : le chemin donné par Marius (`COURS_*.md` ou `making_off/rapport/**.md` d'un projet)
- Reference : `../../_config/schema-fichiers.md`

Do NOT load : les `output/` d'autres runs, les autres étapes, `brainiacs/*/profil/`.

## Process
0. Script : `.venv/bin/python -m freinet.import_projet <document>` écrit `output/source.md` (origine, projet, parties, URLs citées).
1. Lire le document en entier.
2. Compléter `source.md` : concepts candidats (id + une ligne), sources déjà citées (ouvrages « Auteur, Titre (année) », URLs), anecdotes déjà présentes, partie « ancrage projet » (→ futures questions de transfert).
3. `origine:` et `projet:` sont déjà écrits par le script ; ils seront recopiés dans chaque concept.

## Outputs
- `source.md` → output/

## Human check
Vérifier que la liste des concepts candidats couvre les parties du cours, et rayer ce qui n'est qu'ancrage narratif du projet.
