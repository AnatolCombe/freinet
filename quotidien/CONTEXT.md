# quotidien/ — le ticket du matin
> Layer 1. Un run par jour et par élève, lancé par launchd (5 h 57, `freinet.launchd`).

    01_selection   état + bibliothèque → items du jour        (script, reproductible)
    02_plan        plan neutre dans brainiacs/<élève>/plans/  (script + phrase du coach)
    03_rendu       ticket 576 px → Epson TM-m30II-H           (script)
    04_retour      page QR → revue (ajout seul)               (serveur local)

Le ticket sort **sans LLM** et **sans réseau** (inv. 7) : la météo (seul appel réseau, en 02) et la partie générale (`_config/general/`) tombent sans bloquer le ticket. Une question non notée n'est pas un échec (inv. 15).
Les `output/` de ce pipeline contiennent des données d'élève : ignorés par git.

## Le rituel automatique (#53, #44)
- 5 h 57 (réveil à 5 h 55) : `python -m freinet.matin` (sous `caffeinate`) enchaîne 01 → 02 (avec le coach) → 03 pour chaque élève ; idempotent (plan figé, ticket jamais réimprimé) et sous verrou (`data/matin.lock`), donc relancé sans risque au réveil du Mac ou à la main.
- 7 h : `python -m freinet.heartbeat` attend la fin du matin (même verrou), puis alerte (notification macOS) si un ticket n'est pas sorti, si le papier va manquer ou si la page du QR ne répond pas.
- En permanence : `python -m freinet.serveur`, la page du QR (04).
- Journal des agents : `data/journal/*.log` (ignoré par git).

## Mise en service (une fois, par Marius)
1. Imprimante : en **USB** (défaut, `Connexion | usb` dans `_config/imprimante.md`), la brancher au Mac et vérifier `brew list libusb` ; en **Ethernet**, réserver un bail DHCP fixe, écrire `Connexion | ethernet` et son IP. Puis `python -m freinet.rendu --eleve <nom> --imprimer` : le ticket sort, lisible, coupé.
2. Élève : `python -m freinet.eleves ajouter <nom> Europe/Paris` puis `inscrire <nom> <carte> --quete <quête>`.
3. Page du QR : `python -m freinet.serveur`, scanner le QR d'un ticket depuis le téléphone (Wi-Fi de la maison), noter une question ; **puis l'arrêter (Ctrl-C)** : l'agent la reprendra.
4. Alertes : `python -m freinet.heartbeat --essai` ; autoriser les notifications si macOS le demande.
5. Agents : `python -m freinet.launchd afficher` (relire, et lire les avertissements : un dépôt sous ~/Desktop demande l'accès complet au disque pour `.venv/bin/python`, ou un déplacement), puis `python -m freinet.launchd installer` (ou `scripts/installer-launchd.sh`).
6. Réveil : `sudo pmset repeat wakeorpoweron MTWRFSU 05:55:00` (mot de passe administrateur).
7. Vérifier : `scripts/verif-v0.sh` retourne 0 ; le lendemain, relire `data/journal/matin.log` ; à 7 h, aucune alerte.
