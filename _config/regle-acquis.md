# Règle « acquis » — constantes figées (L3)

> Inv. 5. **Le coach ne modifie jamais ce fichier.** Le changer = decision record PRD §6.

| Constante | Valeur |
|---|---|
| `RETENTION_ACQUIS` | 0,85 — rétention FSRS **du concept** (A8 : FSRS suit le concept) prévue à l'horizon ci-dessous, sans révision |
| `HORIZON_ACQUIS_JOURS` | 30 — soit une stabilité d'environ 3 semaines ou plus |
| `TRANSFERT_REQUIS` | 1 — au moins une question de type `transfert` notée ≥ 3 |
| `FSRS_FUZZING` | désactivé (sinon le rejeu diverge, inv. 4) |

États de maîtrise : `verrouille` → `debloque` (prérequis acquis) → `en_cours` (au moins une revue) → `acquis` (règle ci-dessus).
**Acquis reste acquis (A7)** : la règle est évaluée au rejeu après chaque revue ; la première revue qui la satisfait fixe `acquis_le`. L'état ne redescend jamais ; FSRS continue de planifier les révisions.
Une question non notée n'est jamais un échec (inv. 15).
