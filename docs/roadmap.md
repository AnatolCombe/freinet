# Roadmap

Everything below V0 is **planned**. Items are listed as intentions, not commitments, and change as the project learns from use.

## V0 — the morning ticket (implemented)

A single learner receives a printed ticket every morning, built from a real concept map, and each QR rating changes the next ticket.

- SQLite core with an append-only review log, FSRS, the "acquired" rule and exact replay
- Fan-out pipeline `00`-`07` with lateral links, verified anecdotes and a deterministic publication validator
- Daily pipeline `01`-`04`: reproducible selection, plan, thermal ticket, QR feedback page
- Automation (launchd morning job, 07:00 heartbeat), backups, French and English learners
- Check: `scripts/verif-v0.sh` returns 0

Usage criteria set for V0 (not yet reported): seven consecutive tickets without manual intervention, then a 60-day ritual measured by the weekly goal (at least 5 of 7 tickets rated).

## V1 — a living learner profile (planned)

- Onboarding and a deeper interview; profile facts in layers; hypotheses about what helps this learner, tested against evidence
- A weekly coach and a Sunday summary ticket, rendered by the same engine
- A Feynman "teach-back" mode, where the learner explains a concept to a simulated student
- A chat adapter (Telegram or Discord) as a fallback channel, writing through the same path as the QR page
- Map extensions on demand
- Ideas from the backlog: light weeks, saturday free-recall page, interleaved discrimination drills, a drawing area on the ticket, question version hashes in each review, mechanical checking of anecdotes against their source, per-learner FSRS optimisation, visuals written as text (Mermaid, ABC notation) and rendered by a tool

## V2 — first learners beyond the author (planned)

- New maps on declared subjects, enrolment, a channel for each learner, access to the QR page outside the home network
- Ideas from the backlog: content with an expiry date, credited domain reviewers, a trial week on an existing map, consent and erasure for personal data, learner data export, Anki import, implicit repetition through prerequisites

## V3 — a hosted network of learners (planned)

- PostgreSQL, accounts, a web view of the concept map
- Shared maps and quests; "living" concepts enriched by one learner, validated, then appearing in another learner's ticket
- Social acts are about linking concepts, not liking posts

## Vision — the Freinet Box, a solar, offline box for schools (planned)

See [vision.md](vision.md).

## Explicit non-goals

- No "learning styles" (VAK) modelling.
- No LLM decides mastery or the review schedule.
- No punitive gamification: no daily streak, leaderboards or badges.
- No content generated on the fly at print time.
- No free-form chat tutor, no AI grading of written answers.
- No investment advice: finance content is educational, sourced and carries a disclaimer.
- No passive sensors (sleep, mood, screen time).
