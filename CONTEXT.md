# CONTEXT.md — FREINET en un écran
> Layer 1 — routage. Ne contient rien : il pointe.

## Quatre formes ICM composées (PRD §6, B18)

| Dossier | Forme | Unité | Qui écrit |
|---|---|---|---|
| `bibliotheque/` | Knowledge bundle | un concept, une carte, une quête, une question | `fanout/06_publication` uniquement |
| `fanout/` | Pipeline | une carte (sujet nu ou recherche de projet) | LLM + scripts, Marius aux gates |
| `quotidien/` | Pipeline | un ticket, par jour et par élève | scripts ; LLM seulement pour la phrase du coach |
| `brainiacs/` | Record library | un élève | `quotidien/04_retour`, Marius |

Code déterministe : `freinet/` (un seul module parle à `data/freinet.db`, inv. 1).
Fabrique : `_config/`. Méthode : ICM (Interpretable Context Methodology, arXiv:2603.16021).

## Le flux

```
COURS_*.md / rapport ─┐
sujet nu ─────────────┴→ fanout/00→06 ──→ bibliotheque/ ──→ quotidien/01→04 ──→ ticket imprimé
                                                                  ↑                    │
                                              data/freinet.db ←─┴──── retour QR ←────┘
```

## Où aller

| Tu veux… | Lis |
|---|---|
| créer ou étendre une carte | `fanout/CONTEXT.md` |
| comprendre le ticket du matin | `quotidien/CONTEXT.md` |
| le format d'un fichier de contenu | `_config/schema-fichiers.md` |
| les règles qui ne bougent pas | `_config/regle-acquis.md`, `_config/dose.md` |
| la partie générale du ticket (lieu, mots, faits, énigmes) | `_config/general/` (`python -m freinet.general` pour le bilan) |
| l'architecture en anglais | `docs/architecture.md` |
