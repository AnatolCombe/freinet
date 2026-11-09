# brainiacs/ — l'état privé des élèves (Record library)

> Tout ce qui est ici est **privé** (`access_tier: prive`, inv. 11). Les dossiers d'élèves sont ignorés par git.

- `_index/log.md` — le catalogue : une ligne par élève (id, statut `actif|pause|archive`).
- `_templates/brainiac/` — **le tampon** : un nouvel élève naît d'une copie, jamais d'une page blanche.
- `<élève>/profil/` — V0 : `essentiel.md` seul, rempli à la main. Profil vivant = V1.
- `<élève>/plans/` — un plan par jour, écrit par `quotidien/02_plan`.

Les notes, FSRS et la maîtrise vivent dans `data/freinet.db`, pas ici.
