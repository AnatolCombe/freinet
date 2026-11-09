# Privacy

Freinet is built to keep a learner's data on the machine that prints their ticket. This page lists what is stored, where, what leaves the machine, and how to remove it. It describes the code as it is today; anything planned is marked as such.

## What Freinet stores

| Data | Where | Why |
|---|---|---|
| Learner identifier (a short lowercase name, a pseudonym works), time zone, content dosage | `data/freinet.db` (SQLite), table `brainiac` | to plan the day |
| Enrolments (which concept maps, which quest) | SQLite, `inscription` | to pick what to study |
| Daily plans and their status (planned, printed, rated) | SQLite `plan_du_jour` + `brainiacs/<learner>/plans/*.md` | the ticket is printed from the plan |
| Answers to review questions (append-only) and the spaced-repetition state | SQLite `revue`, `fsrs`, `maitrise` | the deterministic engine decides what to review |
| An optional learner profile (goal, time per day) | `brainiacs/<learner>/profil/essentiel.md` | written by the person who runs Freinet |

Freinet does **not** ask for or store age, gender, school, address, e-mail, phone number, photos or location of the learner. The city printed in the weather block is a setting of the installation (`_config/general/general.md`), not learner data.

All of this is plain files: SQLite (standard SQL) and Markdown. They can be read, copied, exported or deleted with ordinary tools.

## What leaves the machine

Nothing is sent anywhere unless one of these optional features is used:

| Feature | What is sent | To whom | How to turn it off |
|---|---|---|---|
| Weather block | the installation's latitude and longitude | Open-Meteo (no account, no key) | `FREINET_SANS_RESEAU=1` |
| Coach sentence | a short text: the date, the title of today's new concept, the number of reviews, the quest progress. **No learner name, no answers, no database access.** | the `claude` command-line tool, run in an empty folder | `FREINET_SANS_LLM=1` (a fixed sentence is printed instead) |
| Building a new concept map (fan-out) | the subject or the course document you choose to import | the LLM agents you run during the fan-out | write maps by hand in Markdown, or do not run the fan-out |

There is no telemetry, no analytics, no account and no cloud storage. Without these options, Freinet works fully offline: the ticket is still printed (inv. 7: every LLM or network step has a deterministic fallback).

## The QR page

The ticket's QR code opens a small page served by the computer that runs Freinet (`python -m freinet.serveur`):

- it only answers clients with a private network address (home or school Wi-Fi);
- each ticket carries a random 128-bit token; only its hash is stored;
- the short typed code is rate-limited per client;
- the server log does not record the token-bearing address.

Running the server on a public Wi-Fi is discouraged (see `_config/retour.md`).

## Removing a learner's data

Today, removal is manual: delete the learner's folder `brainiacs/<learner>/` and their rows in `data/freinet.db` (all state tables carry `brainiac_id`). A one-command `forget` is **planned** (see the roadmap). Backups made with `freinet.sauvegarde` must be deleted too.

## Responsibility

Freinet is software you install and run yourself. Whoever runs it (a parent, a teacher, a school) is responsible for the data it holds and for applicable law, such as the GDPR in the European Union. Freinet's design (local storage, no identity data, pseudonyms, optional network) is meant to make that easy.

Questions or concerns: see [SECURITY.md](../SECURITY.md).
