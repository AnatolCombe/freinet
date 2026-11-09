# API ADVIZA (L3)

| Clé | Valeur |
|---|---|
| Port | 8766 |

- **Écoute** : toujours `127.0.0.1`, non réglable, car ADVIZA tourne sur le même Mac. L'API est servie par le processus de la page du QR (`python -m freinet.serveur`). Sans jeton ci-dessous, elle ne démarre pas.
- **Jetons** : un par compte ADVIZA, chacun lié à un seul élève (`brainiac_id`). Seule l'empreinte SHA-256 figure ici. Pour créer un jeton : `uv run python -m freinet.adviza_jetons nouveau <élève>` (le clair ne s'affiche qu'une fois). Pour révoquer : retirer la ligne, puis relancer la page du QR. Contrat : `quotidien/04_retour/CONTEXT.md` (API ADVIZA).

## Jetons (empreinte → élève) — table en fin de fichier

| brainiac_id | empreinte |
|---|---|
