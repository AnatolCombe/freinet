# sources/ — registre des sources de confiance (#47)

Un fichier par domaine. `fanout/05_verification` **rejette** une anecdote ou un fait dont la source n'est pas sous un domaine listé ici. Ajouter une source = une ligne, avec la raison.

**Règle mécanique** (`freinet/sources.py`) : une URL http(s) est admise si son hôte (ou un sous-domaine) et son préfixe de chemin figurent dans le fichier du domaine du concept ou dans `culture.md`. Un **ouvrage publié** cité « Auteur, Titre (année) » est admis mécaniquement mais vérifié à la gate humaine de `05_verification`. Tout le reste est refusé par `06_publication`.

**Ne jamais lister un hôte multi-locataire** (`pressbooks.pub`, `github.io`, `substack.com`…) sans préfixe de chemin : tout sous-domaine d'une entrée est admis.
