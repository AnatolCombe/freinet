# Page du QR (L3)

| Clé | Valeur |
|---|---|
| Écoute | 0.0.0.0 |
| Port | 8765 |
| Adresse du QR | auto |
| QR vers ADVIZA | aucune |

- **Écoute** : adresse où `python -m freinet.serveur` écoute. Les clients hors réseau privé
  sont refusés de toute façon ; `127.0.0.1` pour un essai sur le Mac seul.
- **Adresse du QR** : ce que le téléphone ouvre. `auto` = `http://<nom du Mac>.local:<port>`
  (Bonjour). Sinon une adresse complète, ex. `http://192.168.1.20:8765`.
- **QR vers ADVIZA** : `aucune` (le QR ouvre l'espace du ticket ici) ou l'adresse d'ADVIZA, ex. `http://<nom du Mac>.local:8000` ; le QR ouvre alors `<adresse>/profil/freinet/aujourdhui` (PROF-A). Ne régler qu'une fois les pages FREINET d'ADVIZA livrées (PROF-B). Le code court imprimé reste celui de cette page (`/c`).
- **Réseau** : seuls les clients d'adresse privée sont servis (10/8, 172.16/12, 192.168/16…).
  Sur un Wi-Fi public (café, hôtel), ces voisins sont aussi « privés » : le jeton et la limite
  des essais de code protègent la page, mais mieux vaut ne pas lancer le serveur hors de chez soi.
- Hors du Wi-Fi de la maison : Tailscale (V2, #22 ; son réseau 100.64/10 est refusé en V0).
- **Pages de cours** : `http://<nom du Mac>.local:<port>/cours` depuis n'importe quel appareil du
  Wi-Fi de la maison (sans ticket) ; chaque fiche : `/fiche/<concept>`. Avec le QR, les mêmes
  pages s'ouvrent dans l'espace du ticket (`/r/<jeton>/cours`, onglets Aujourd'hui · Ma carte · Cours).

L'espace d'un ticket prend la langue de son plan (`langue:`) : libellés (`freinet/libelles_espace.py`) et bibliothèque (`bibliotheque/en/`) ; les pages ouvertes (`/cours`, `/fiche`, `/c`) restent en français (PROF-12).
