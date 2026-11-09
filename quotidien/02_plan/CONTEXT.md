# 02_plan — écrire le plan du jour

One job : Le plan neutre, modifiable, que tous les canaux mettent en forme (B4).

## Inputs
- Working : la `Selection` de `01_selection` (même processus)
- Reference : `freinet/coach.py` (consigne du coach, règles de la phrase) ; le LLM ne reçoit que le résumé texte du jour (`coach.contexte`), jamais la base (inv. 2)
- Reference : `_config/general/` (partie générale : lieu, profils, mots, faits, énigmes ; `freinet/general.py`) et la météo du jour d'Open-Meteo (`freinet/meteo.py`, seul appel réseau du passage, délai 5 s)

Do NOT load : les `output/` d'autres runs, les autres étapes, `brainiacs/*/profil/`.

## Process
1. Publier `brainiacs/<élève>/plans/AAAA-MM-JJ.md` (`freinet/plan.py`) s'il n'existe pas encore, par lien dur d'un fichier complet (jamais de fichier à moitié écrit ; de deux passages simultanés, le premier gagne) : frontmatter (items à noter pour la page QR, source de l'anecdote) + corps neutre (pas de consigne propre au papier ; phrase, énoncés, fil d'Ariane et défi ramenés à une ligne ; leçon et anecdote insérées telles quelles, contenu validé de la bibliothèque).
2. Le fichier fait foi : un plan déjà écrit est figé (relancer le rend tel quel, retouche à la main conservée), et chaque passage resynchronise `plan_du_jour` sur sa notion `nouvelle` (`Base.fixer_plan`). Pour refaire le plan d'un jour, supprimer le fichier.
3. Phrase du coach (#19) : `claude -p` (modèle léger, sans outils, délai 60 s) sur le résumé du jour ; réponse contrôlée (une ligne, ≤ 90 caractères, sans lien, imprimable). Au moindre écart, ou avec `FREINET_SANS_LLM=1` / `--sans-coach`, la phrase par défaut sort (inv. 7). Écrite une fois, avec le plan.
4. Partie générale (PROF-8) : bloc du jour par la seule date, commun à tous les élèves (`freinet/partie_generale.py`), et météo résolue une fois, écrits dans le plan et figés avec lui (réimpression sans réseau, même ticket). Liste générale invalide ou météo indisponible : le plan sort sans elles et l'erreur va au journal (inv. 7, décision B du 2026-09-30).

## Outputs
- `brainiacs/<élève>/plans/AAAA-MM-JJ.md` ; clé `demain` de l'en-tête (si une notion est promise, #126) et section `## À lire pour demain` (son titre), imprimée telle quelle par le ticket ; `langue: en` pour un élève anglophone (absente = français), titres dans la langue (`freinet/langue.py`, PROF-12)

## Human check
Optionnel : relire le plan avant l'impression ; le rendu lit ce qui est écrit.
