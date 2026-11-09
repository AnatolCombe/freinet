# Imprimante (L3)

| Clé | Valeur |
|---|---|
| Modèle | Epson TM-m30II-H (M362D) |
| Connexion | usb |
| IP | à renseigner si Connexion = ethernet (bail DHCP fixe sur la box) |
| Port | 9100 |
| État automatique (ASB) | coupé par le logiciel à chaque connexion (`GS a 0`) |
| Papier | 80 mm, **sans bisphénol** (#38) |
| Largeur de rendu | 576 px (≈ 48 colonnes police A) |
| Repli | Telegram (V1), sinon `brainiacs/<élève>/plans/*.md` et `quotidien/03_rendu/output/<élève>/` |

`Connexion` vaut `usb` ou `ethernet` (lu par `freinet/imprimante.py`).
- **usb** : ESC/POS brut par libusb (`pyusb`, `brew install libusb`), l'imprimante reconnue par
  ses identifiants (Epson `0x04B8`, TM-m30II-H `0x0E2A`). `IP` et `Port` sont ignorés.
- **ethernet** : ESC/POS brut sur `IP:Port`.

Dans les deux cas : état vérifié avant (`DLE EOT`), sortie confirmée après (`GS r 1`).

Essai : `python -m freinet.rendu --eleve <nom> --imprimer` (ou `--imprimante usb` /
`--imprimante <ip>` pour ne pas toucher à ce fichier).
