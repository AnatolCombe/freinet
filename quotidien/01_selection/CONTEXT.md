# 01_selection — choisir les items du jour

One job : Script déterministe : même graine (date logique + élève) et même état → même plan (inv. 6).

## Inputs
- Working : `data/freinet.db` (via `freinet/`, jamais directement) · `../../bibliotheque/`
- Reference : `../../_config/dose.md` · `../../_config/regle-acquis.md`

Do NOT load : les `output/` d'autres runs, les autres étapes, `brainiacs/*/profil/`.

## Process (`freinet/selection.py`, lancé par `python -m freinet.quotidien --eleve <nom>`)
1. Révisions échues (FSRS, concept canonique) : les plus fragiles d'abord, plafonnées par la dose (#50, inv. 14) ; pour chaque concept, la question la moins récemment posée, pré-tests exclus (le format tourne, A8). Non notée = reste due (inv. 15).
2. Notion nouvelle, jamais une notion déjà présentée (ticket imprimé ou noté ; un plan jamais imprimé ne compte pas) : tirage pondéré projets / déclarés / sérendipité (graine date + élève) ; « sérendipité » = premier concept débloqué atteint par un lien latéral depuis un concept déjà vu, sinon le premier débloqué ; week-end 0/0/100 (A2), la dose ne change pas. Premier concept débloqué dans l'ordre des prérequis. Une notion présentée mais jamais notée revient le lendemain en premier rappel ; déclarée « je sais déjà » sur la page du QR (#26), ce premier rappel est une question de transfert. Sa question `pre_test` est posée **sur le même ticket, avant la leçon** (#7).
3. Sérendipité : un lien latéral qui touche un concept connu (#8).
4. Anecdote : d'abord celle d'un concept du jour, sinon d'un concept de la carte ; défi au format tournant (#24, #37).
5. Mode reprise si du travail attend une réponse (révision échue, notion présentée jamais notée) depuis ≥ 3 jours logiques sans aucun scan : pas de notion nouvelle, questions les plus faciles, fil d'Ariane (#11). Rien d'échu = jamais de reprise.
- **Notion de demain (#126)** : le passage du jour J calcule aussi la notion nouvelle de J+1 (`notion_de_demain` : même sélection le lendemain à la même heure, la notion du jour comptée comme présentée, sans reprise). Le lendemain, cette promesse (clé `demain` du plan de la veille) passe devant le tirage si elle est dans la carte et jamais présentée. Jour de reprise : pas de notion nouvelle, la promesse est reportée telle quelle.

## Outputs
- en mémoire : `Selection`, passée à `02_plan` (pas de fichier intermédiaire).

## Human check
Aucune : étape déterministe, couverte par les tests (inv. 6).
