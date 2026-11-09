# fanout/ — fabriquer une carte
> Layer 1. Une carte = un run. Lancé par Marius dans Claude Code (B16).

## Deux entrées (B28)

| Entrée | Démarre à | Ce qu'on donne |
|---|---|---|
| **Recherche de projet** | `00_import` | un chemin : `<projet>/making_off/COURS_*.md` ou `making_off/rapport/**.md` |
| **Sujet nu** | `01_cadrage` | un sujet + l'élève visé |
| **Extension** | `01_cadrage` | « étendre autour de X » + la carte existante |
| **Traduction** | `07_traduction` | une carte publiée + la langue (`en`), puis `06_publication` |

## Le pipeline

```
00_import        document de projet → source.md                       (script + LLM)
01_cadrage       objectif, périmètre, niveau, quêtes candidates        (LLM)   GATE LOURDE
02_carte         concepts + prérequis + latéraux + quêtes              (LLM + script)  GATE LOURDE
03_redaction     un agent par concept nouveau                          (agents en parallèle)
04_questions     4 à 6 questions typées par concept                    (agents en parallèle)
05_verification  faits contre sources, élève simulé, grille LearnLM    (agents)  GATE LOURDE
06_publication   validation + échange dans bibliotheque/ + index       (script, sans LLM ; commit par l'opérateur)
07_traduction    un agent par concept : jumeau traduit (en/…), puis 06  (agents en parallèle ; PROF-12)
```

Statut d'un run : les fichiers présents dans `*/output/`. Un run se reprend à l'étape où il s'est arrêté. **Un run commence avec des `output/` vides** : `06_publication` archive les sorties d'un run publié dans `fanout/_publies/<horodatage>/` (hors git).
Les agents qui lisent le web n'écrivent jamais hors de leur `output/` et ne committent jamais (#45).
