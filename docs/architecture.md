# Architecture

Freinet is two pipelines around one deterministic engine:

- **fan-out** (`fanout/`) turns a subject into a validated concept map, once per subject;
- **daily** (`quotidien/`) turns the learner's state and the library into one printed ticket per day, and records the feedback.

Everything a human or an LLM reads is a text file (Markdown with YAML front matter). Everything machines write is in one SQLite database (`data/freinet.db`, git-ignored).

```text
project notes ─┐
bare subject ──┴→ fanout/00→06 ──→ bibliotheque/ ──→ quotidien/01→04 ──→ printed ticket
                                                            ↑                     │
                                       data/freinet.db ←──┴───── QR feedback ←──┘
```

Identifiers in the code are French. A short glossary: *élève* learner, *carte* concept map, *quête* quest, *revue* review, *acquis* acquired, *notion nouvelle* new concept, *rendu* rendering, *retour* feedback, *bibliothèque* library, *sérendipité* serendipity, *dose* daily amount.

## Folder roles

The repository follows the Interpretable Context Methodology (ICM, arXiv:2603.16021): each pipeline stage is a folder with a `CONTEXT.md` contract (inputs, process, outputs, one human check), checked by `scripts/verif-contrats.py`.

| Folder | Role | Unit | Who writes |
|---|---|---|---|
| `bibliotheque/` | knowledge bundle: shared content | a concept, a map, a quest, a question | `fanout/06_publication` only |
| `fanout/` | pipeline | one concept map | LLM agents + scripts, a human at the gates |
| `quotidien/` | pipeline | one ticket per day per learner | scripts; an LLM only for the optional coach sentence |
| `brainiacs/` | record library: private learner state | one learner | the daily pipeline and the operator |
| `_config/` | stable configuration ("factory") read by the code | one concern per file | humans |
| `freinet/` | the deterministic engine | one responsibility per file | developers |

## Fan-out stages

| Stage | Does | Run by |
|---|---|---|
| `00_import` | a project's course or research document → `source.md` | script (`python -m freinet.import_projet`) + LLM |
| `01_cadrage` | goal, scope, level, candidate quests | LLM, heavy human gate |
| `02_carte` | concepts, prerequisites, lateral links, quests | LLM + script, heavy human gate |
| `03_redaction` | one agent per new concept: lesson, long version, analogies, sourced anecdotes | parallel LLM agents |
| `04_questions` | 4 to 6 typed questions per concept | parallel LLM agents |
| `05_verification` | facts against sources, simulated learner, review rubric | LLM agents, heavy human gate |
| `06_publication` | full validation, atomic swap into `bibliotheque/`, index regeneration | script only (`python -m freinet.publication`) |
| `07_traduction` | translated twin of a published map (`bibliotheque/en/`), then `06` | parallel LLM agents |

Agents that read the web treat sources as hostile: they write only to their stage's `output/`, never commit, and their text is checked to be plain text without links or markup before publication.

## Daily stages

| Stage | Does | Module |
|---|---|---|
| `01_selection` | state + library → items of the day, reproducible (seed = date + learner) | `selection.py` |
| `02_plan` | items → neutral Markdown plan in `brainiacs/<learner>/plans/`, written once and never overwritten | `plan.py`, `quotidien.py` |
| `03_rendu` | plan → 576 px 1-bit PNG + 48-column text → ESC/POS printer | `ticket.py`, `rendu_png.py`, `rendu.py`, `imprimante.py`, `liaison.py` |
| `04_retour` | QR page → one append-only review row per rating | `serveur.py`, `retour.py`, `espace.py`, `acces.py` |

`python -m freinet.matin` chains 01 → 03 for every learner (idempotent, under a file lock); `python -m freinet.heartbeat` checks at 07:00 that every ticket came out; `python -m freinet.launchd` installs both as macOS launchd agents.

## Modules (`freinet/`)

| Module | Responsibility |
|---|---|
| `base/` | **the only package that talks to SQLite**: migrations, WAL, append-only `revue` log, `fsrs` and `maitrise` caches rewritten under one lock, daily plans, hashed QR accesses, idempotent API requests, in-memory FTS5 index |
| `temps.py` | UTC ISO 8601 instants, logical date in the learner's time zone |
| `constantes.py` | reads `_config/regle-acquis.md`; no threshold is copied into the code |
| `modele.py` | `Revue`, `EtatConcept`: plain data objects |
| `planification.py` | FSRS per learner × concept (`fsrs` 6.3.2, fuzzing off) |
| `acquis.py` | the pure "acquired" rule |
| `rejeu.py` | review log → state, total order, corrections resolved in chain, acquisition dated once |
| `etat.py` | recomputes a learner's caches; checks they equal the replay |
| `sauvegarde.py` | atomic `VACUUM INTO` backups; restore validation on a throwaway copy |
| `frontmatter.py`, `contenu.py` | content files → typed `Concept`, `Carte`, `Quete`, `Question` |
| `graphe.py` | map validation (cycles, orphans, unknown ids), unlock order, mastery states |
| `bibliotheque.py` | loads and validates the library; aliases for renamed concepts |
| `recherche.py` | top-5 existing concepts for a candidate (FTS5), cross-domain homonyms flagged |
| `mermaid.py` | map → Mermaid `graph TD`, coloured by mastery |
| `index.py` | generated `bibliotheque/index.md` |
| `sources.py`, `validation.py` | trusted-source registry; content rules (sourcing, finance disclaimer, printable characters, question mix) |
| `publication.py` | staging tree → validation → atomic swap with rollback → index → archive |
| `import_projet.py` | script part of `00_import` |
| `dose.py` | bounds from `_config/dose.md` |
| `selection.py` | reviews, new concept + pre-test, serendipity, anecdote, challenge, quest, restart |
| `langue.py`, `libelles_espace.py` | French and English labels |
| `plan.py`, `quotidien.py` | the plan of the day and the morning pass |
| `general.py`, `partie_generale.py`, `meteo.py` | general section (word of the day, on this day, puzzle) and optional weather |
| `ticket.py`, `imprimable.py`, `rendu_png.py`, `rendu.py` | ticket content, printable glyphs, bitmap rendering, CLI |
| `liaison.py`, `imprimante.py` | USB/TCP transport; raw ESC/POS with status before and confirmation after |
| `acces.py` | 128-bit tokens and short codes, stored as HMAC with a local key |
| `retour.py`, `espace.py`, `pages.py`, `serveur.py` | feedback logic, the learner's ticket space, open course pages, hardened `http.server` |
| `coach.py` | the only LLM call in the morning (`claude -p`), with output checks and a default fallback |
| `eleves.py` | add a learner, enrol in a map |
| `matin.py`, `heartbeat.py`, `launchd.py`, `verrou.py` | scheduling, alerting, single-run lock |
| `api_adviza.py`, `adviza_*.py` | optional local JSON API for an external front-end (see below) |

Every file stays under 400 lines.

## Data model

Migrations live in `migrations/NNN_*.sql`. Tables: `brainiac` (learners), `inscription` (enrolments), `revue` (the review log), `fsrs` and `maitrise` (caches recomputed from `revue`), `plan_du_jour` (daily plans and their status), `adviza_requete` (idempotency keys of the optional API). Every state table carries `brainiac_id`, so the schema is ready for several learners. Triggers make `revue` and `adviza_requete` append-only.

A rating correction is a new `revue` row pointing at the one it corrects (`corrige_id`), never an UPDATE.

## Invariants

These are enforced by tests or scripts:

1. Only `freinet/base/` imports `sqlite3` or executes SQL.
2. An LLM never reads the database: LLM stages receive declared text exports.
3. `revue` only grows (SQL triggers).
4. State is fully recomputable: replaying `revue` yields identical FSRS state and mastery.
5. "Acquired" = predicted concept retention ≥ 0.85 at 30 days without review **and** ≥ 1 successful transfer question; once acquired, always acquired. Constants in `_config/regle-acquis.md`.
6. Selection is reproducible: same seed (date + learner) and state, same plan.
7. The ticket prints without an LLM.
8. No map is published with a prerequisite cycle, an orphan concept or an unknown id.
9. Every anecdote and every finance concept carries a source; finance carries a disclaimer.
10. Every state table carries `brainiac_id`.
11. The private profile never leaves `brainiacs/<learner>/`.
12. Every stage folder has an ICM `CONTEXT.md` contract.
13. Generated indexes are never edited by hand (`scripts/regen-index.py --check`).
14. Bounded dose: at most N reviews and 1 new concept per ticket.
15. An unrated question is never counted as a failure.

`scripts/verif-v0.sh` runs the end-to-end check: on a fresh database it publishes the demo map, renders day 1, posts a simulated QR rating to the real server, checks that day 2 reflects FSRS (a failed concept comes back, a passed one is pushed back), checks the replay, then runs the full test suite, the index check and the contract check.

## Security of the QR page

The QR page (`serveur.py`) serves private network addresses only, restricts the `Host` header, requires a same-origin `Origin` (or `Sec-Fetch-Site`) on POST, bounds request bodies and time, limits connections per client and short-code attempts, expires old accesses, sends strict headers (CSP, no cache) and never logs tokens. Tokens and short codes are random and stored only as HMACs keyed by a local secret (`data/.cle-acces`, excluded from backups).

## Optional integration: local JSON API

`api_adviza.py` exposes a small JSON API (`/adviza/*`, contract v1) for an external front-end running on the same machine. It is **off by default**: it starts only if at least one token fingerprint is listed in `_config/adviza.md`. It listens on `127.0.0.1` only, refuses browsers, maps each bearer token to exactly one learner, offers named reads (`etat`, `aujourdhui`, `cartes`, `concept`, `catalogue`) and three idempotent actions (`noter`, `joker`, `choisir_carte`) that go through the same code path as the QR page. The front-end never touches the database. The name comes from the companion application it was written for; nothing in Freinet depends on it.

## Platform notes

The core (library, engine, rendering, QR page) is plain Python. Scheduling (`launchd.py`), desktop notifications (`heartbeat.py`) and Bonjour host names (`acces.py`) are macOS-specific today.
