# 03_rendu — mettre en forme et imprimer

One job : Adaptateurs : ticket thermique (V0), Telegram (V1).

## Inputs
- Working : `brainiacs/<élève>/plans/AAAA-MM-JJ.md` (le fichier fait foi : une retouche passe sur le ticket)
- Reference : `../../_config/imprimante.md`, `../../_config/retour.md` ; `bibliotheque/` (réponses du pli, domaine finance) ; `data/freinet.db` (élève, statut du plan)

Do NOT load : les `output/` d'autres runs, les autres étapes, `brainiacs/*/profil/`.

## Process (`python -m freinet.rendu --eleve <nom> [--jour AAAA-MM-JJ] [--imprimer]`)
1. Lire le ticket dans le plan (`freinet/ticket.py`) : questions reconnues sous « Révisions » seulement, pré-test sous « Nouveau · … » ; textes nettoyés (NFC, sans caractère de contrôle) ; source web réduite à l'hôte (#45) ; avertissement finance ajouté dès qu'un concept du jour est de ce domaine (inv. 9, B26). Le ticket relit `langue:` dans le plan : sections, pli, consigne et date dans cette langue (PROF-12).
2. Rendu bitmap 576 px, 1 bit (`freinet/rendu_png.py`, Pillow en mise en page BASIC + police DejaVu embarquée ; un caractère hors police devient « ? », et le fan-out le refuse déjà) + QR (segno) de la page du retour et son code court (#34), les mêmes d'un rendu à l'autre du jour (`freinet/acces.py`, clair dans `output/<élève>/acces-AAAA-MM-JJ.txt`, 0600) ; `--nouvel-acces` les renouvelle, `--sans-qr` s'en passe.
3. Pli de réponse : une ligne pointillée sous chaque question, les réponses imprimées à l'envers sous un pointillé ✂ (#14).
4. `--imprimer` : ESC/POS brut par USB ou sur le port 9100 selon `_config/imprimante.md` (`freinet/imprimante.py`, transport dans `freinet/liaison.py`) ; état vérifié avant (`DLE EOT` : hors ligne, capot, papier), sortie confirmée après (`GS r 1`) ; alors seulement le plan est marqué imprimé — sa notion compte comme présentée. Non confirmé → code 3, ticket et plan conservés (repli ; alerte heartbeat #44 avec PROF-7). Après un code 3 : vérifier le papier et le capot avant de relancer (un rouleau changé en cours d'impression fait sortir la fin du ticket) ; si le ticket est sorti, `--remis`. `--remis` : ticket lu à l'écran, marqué remis sans imprimer.
5. Le QR ouvre `<QR vers ADVIZA>/profil/freinet/aujourdhui` si `_config/retour.md` le règle (PROF-A), sinon l'espace du ticket ; le code court reste celui de la page du QR.

## Outputs
- `output/<élève>/ticket-AAAA-MM-JJ.png` + `.txt` (ignorés par git : données d'élève)
- `plan_du_jour.statut` = `imprime` dans `data/freinet.db` (ticket sorti ou remis)

## Human check
Le ticket en main, au café : il est sorti, lisible, coupé.
