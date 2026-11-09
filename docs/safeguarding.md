# Safeguarding and "do no harm"

Freinet may be used by children. This page says how the design protects them, what it does not do, and what remains to be done before any use in schools.

## Children's data

- **Minimal data by design.** A learner is a pseudonym and a time zone. No age, school, contact details, photo or location is asked for or stored (see [privacy.md](privacy.md)).
- **Local by default.** Data stays on the machine that prints the ticket; nothing is shared with other learners or with a server.
- **No profiling by a model.** No language model reads the database. Mastery and review are decided by a deterministic engine whose rules are written in `_config/regle-acquis.md`.

## Content

- **Nothing is generated at print time.** Every lesson, question and anecdote is drafted during the fan-out, then checked by a human and by the publication gate (`python -m freinet.publication`) before it can reach a ticket.
- **Sources are required.** Every anecdote must cite a source from a per-domain registry of trusted sources; unsourced content is refused.
- **Bounded model output.** The only text written by a model on the day is one coach sentence: one line, at most 90 characters, no link, printable characters only. Anything else is replaced by a fixed sentence.
- **Sensitive topics.** Finance content must be sourced and carries an "educational, not investment advice" notice. Freinet does not give medical, legal or financial advice.

## Wellbeing

- **No punitive gamification.** There is no streak that breaks, no ranking, no badge. After a pause, the next ticket says there is nothing to catch up and restarts gently.
- **Paper, not a screen.** The daily ticket is printed, so a child does not need a phone or an account to use it.

## Contact between people

Freinet V0 has **no** messaging, comments, profiles visible to others or social features, so there is no channel for harassment or contact with strangers. The "network of learners" in the roadmap is **planned only**; it will not ship without a safeguarding review, moderation and parental or school controls.

## Before use in schools (planned)

The [vision](vision.md) of an offline school box would put Freinet in front of many children. Before any pilot:

- a data protection impact assessment with the partner school or authority;
- consent and information sheets for families, in the local language;
- the one-command `forget` for a learner's data;
- teacher validation of every locally generated lesson (the teacher always approves before use).

## Reporting a problem

Harmful content, a privacy issue or a security flaw: follow [SECURITY.md](../SECURITY.md). Reports about children are handled first.
