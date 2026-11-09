---
ville: "Lyon"
latitude: 45.74846
longitude: 4.84671
fuseau: "Europe/Paris"
origine: "2026-10-01"
seuil_pluie: 20
langues: ["roumain", "allemand", "anglais", "espagnol", "hébreu"]
langues_en: ["roumain", "allemand", "français", "espagnol", "hébreu"]
eleves: {}
---

# Partie générale du ticket (L3)

> Lu par `freinet/general.py`.

- **Lieu** : exemple (Lyon) ; remplacer par la ville de l'élève, coordonnées du géocodeur
  Open-Meteo. `ville` est le nom court imprimé.
- **Origine** : premier jour de la rotation des mots (langue du jour = rang depuis l'origine,
  modulo 5). La changer décale tous les mots à venir.
- **Seuil de pluie** : 20 %, valeur de départ **à calibrer** après deux semaines de tickets
  (au-dessous, le moment de la pluie n'est pas imprimé).
- **Profils** : `prenom` en tête du ticket ; `mot_de` ajoute « Un mot de … » à écrire au stylo.
  Un élève absent ici a son nom en majuscules pour prénom, sans mot de l'autre.
  `langue` (`fr` par défaut, ou `en`) : langue du plan, du ticket et de l'espace ; un élève `en`
  lit `en/mots.md`, `en/ce-jour-la.md`, `en/enigmes.md` et la rotation `langues_en` (même nombre
  de langues que `langues`, même rang). Ne pas passer un élève en `en` avant que `en/` existe
  (PROF-12e) : sinon son ticket sort sans partie générale.
